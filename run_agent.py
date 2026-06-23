import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Union

from dotenv import load_dotenv

from tools import (
    fetch_mausamgram_forecast,
    fetch_mausamgram_forecast_tool,
    list_known_locations,
    lookup_location,
    parse_imd_bulletins,
    resolve_location,
    scrape_imd_press_release_urls,
)


load_dotenv()

FORECAST_MODES = ("1hr", "3hr", "6hr", "daily")


def _json_loads(value, fallback):
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _clip(text, limit=1200):
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch a location forecast from Mausamgram and national context from IMD press releases."
    )
    parser.add_argument("--place", help="Known place name from master.csv, e.g. Chennai.")
    parser.add_argument("--query", help="Custom question for the AI agent (bypasses interactive prompt).")
    parser.add_argument("--lat", type=float, help="Latitude for direct Mausamgram lookup.")
    parser.add_argument("--lon", type=float, help="Longitude for direct Mausamgram lookup.")
    parser.add_argument("--forecast", choices=FORECAST_MODES, help="Forecast interval: 1hr, 3hr, 6hr, or daily.")
    parser.add_argument("--json-out", help="Write normalized output JSON to this path.")
    parser.add_argument("--skip-imd", action="store_true", help="Skip IMD press-release fetch and parse.")
    parser.add_argument("--skip-mausamgram", action="store_true", help="Skip Mausamgram API fetch.")
    parser.add_argument("--agent", action="store_true",
                        help="Run the LLM ReAct agent instead of the fast direct forecast mode.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose LLM output.")
    return parser.parse_args()


def _prompt_forecast_mode():
    print("Choose forecast interval:", flush=True)
    print("  1. 1hr   - 1-hour forecast for about 1.5 days", flush=True)
    print("  2. 3hr   - 3-hour forecast for about 5 days", flush=True)
    print("  3. 6hr   - 6-hour forecast for about 10 days", flush=True)
    print("  4. daily - daily forecast", flush=True)
    choices = {"1": "1hr", "2": "3hr", "3": "6hr", "4": "daily"}
    while True:
        value = input("Forecast mode [1hr/3hr/6hr/daily]: ").strip().lower()
        value = choices.get(value, value)
        if value in FORECAST_MODES:
            return value
        print("Please enter one of: 1hr, 3hr, 6hr, daily.", flush=True)


def _prompt_location(args):
    if args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            raise ValueError("Provide both --lat and --lon for coordinate lookup.")
        return resolve_location(place=args.place, lat=args.lat, lon=args.lon)

    if args.place:
        return resolve_location(place=args.place)

    value = input("Enter place name or latitude,longitude: ").strip()
    if "," in value:
        lat_text, lon_text = [part.strip() for part in value.split(",", 1)]
        return resolve_location(lat=lat_text, lon=lon_text)

    try:
        return resolve_location(place=value)
    except ValueError as exc:
        print(str(exc), flush=True)
        lat_text = input("Latitude: ").strip()
        lon_text = input("Longitude: ").strip()
        return resolve_location(place=value, lat=lat_text, lon=lon_text)


def _fetch_imd_context():
    urls_json = scrape_imd_press_release_urls.invoke({"query": ""})
    urls = _json_loads(urls_json, [])
    if not isinstance(urls, list) or not urls:
        return {"status": "error", "error": urls_json}

    max_pdfs = int(os.getenv("MAX_IMD_PDFS", "1"))
    selected_urls = urls[:max_pdfs]
    parsed_json = parse_imd_bulletins.invoke({"urls": selected_urls})
    parsed = _json_loads(parsed_json, [])
    if isinstance(parsed, dict):
        return {"status": "error", "error": parsed.get("error", parsed)}
    if not parsed:
        return {"status": "error", "error": "No IMD bulletin data was extracted."}

    bulletin = next((item for item in parsed if not item.get("error")), parsed[0])
    return {
        "status": "ok" if not bulletin.get("error") else "error",
        "source_url": bulletin.get("source_url", selected_urls[0]),
        "document_type": bulletin.get("document_type", "IMD bulletin"),
        "sections": {
            key: bulletin.get(key)
            for key in (
                "forecast",
                "weather_forecast",
                "rainfall_warnings",
                "warning",
                "impact_expected",
                "action_suggested",
            )
            if bulletin.get(key)
        },
        "raw": bulletin,
    }


def _format_record(record):
    if isinstance(record, dict):
        preferred = []
        for key in (
            "time",
            "date",
            "datetime",
            "valid_time",
            "temp",
            "temperature",
            "rainfall",
            "rain",
            "rh",
            "humidity",
            "wind_speed",
            "wind",
            "weather",
            "cloud",
        ):
            if key in record and record[key] not in (None, ""):
                preferred.append(f"{key}={record[key]}")
        if preferred:
            return ", ".join(preferred)
        return _clip(json.dumps(record, ensure_ascii=False), 400)
    return _clip(record, 400)


def _print_human_summary(result):
    location = result["location"]
    print("\n--- Agent Response ---", flush=True)
    print(
        f"Location: {location['name']} ({location['lat']}, {location['lon']})",
        flush=True,
    )
    print(f"Forecast mode: {result['forecast_mode']}", flush=True)

    mausamgram = result.get("mausamgram")
    if mausamgram:
        print("\nLocal Mausamgram Forecast:", flush=True)
        print(f"Source: {mausamgram.get('endpoint')}", flush=True)
        if mausamgram.get("status") == "error":
            print(mausamgram.get("error"), flush=True)
        elif mausamgram.get("status") == "parser_warning":
            print(mausamgram.get("parser_warning"), flush=True)
            print(_clip(mausamgram.get("raw_response", ""), 1600), flush=True)
        else:
            records = mausamgram.get("records") or []
            if records:
                for idx, record in enumerate(records[:8], start=1):
                    print(f"  • Day {idx}: {_format_record(record)}", flush=True)
                if len(records) > 8:
                    print(f"  ... {len(records) - 8} more records in normalized JSON.", flush=True)
            else:
                print("Mausamgram returned JSON, but no forecast records were recognized.", flush=True)

    imd = result.get("imd_press_release")
    if imd:
        print("\nNational IMD Bulletin Context:", flush=True)
        print(f"Source: {imd.get('source_url')}", flush=True)
        print(f"Document type: {imd.get('document_type')}", flush=True)
        if imd.get("status") == "error":
            print(imd.get("error"), flush=True)
        else:
            sections = imd.get("sections") or {}
            if sections:
                for key, value in sections.items():
                    formatted_val = str(value).replace("➢", "\n  • ").replace("❖", "\n  • ")
                    print(f"\n{key.replace('_', ' ').title()}:\n  {formatted_val.strip()}", flush=True)
            else:
                print("No forecast/warning sections were extracted from the latest bulletin.", flush=True)


def _prompt_user_query():
    prompts = [
        "What is the latest weather forecast from the IMD?",
        "Are there any heavy rainfall warnings in the latest bulletin?",
        "Summarize the impact expected from heat waves.",
        "Give me the latest update on cyclones or depressions."
    ]
    print("\nChoose a question to ask the AI agent:", flush=True)
    for i, p in enumerate(prompts, 1):
        print(f"  {i}. {p}", flush=True)
    print(f"  {len(prompts) + 1}. Type your own custom question...", flush=True)
    
    while True:
        choice = input(f"Select [1-{len(prompts) + 1}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(prompts):
            return prompts[int(choice) - 1]
        elif choice == str(len(prompts) + 1):
            return input("\nEnter your custom query: ").strip()
        else:
            print("Invalid choice.", flush=True)

def run_direct_forecast(args):
    location = _prompt_location(args)
    forecast_mode = args.forecast or _prompt_forecast_mode()
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "location": location,
        "forecast_mode": forecast_mode,
        "mausamgram": None,
        "imd_press_release": None,
    }

    # Run both network fetches in parallel to save wall-clock time
    def _fetch_mausamgram():
        return fetch_mausamgram_forecast(
            location["lat"], location["lon"], forecast_mode,
            place_name=location.get("name", ""),
        )

    fetches = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        if not args.skip_mausamgram:
            print("Step 1/3: Fetching Mausamgram point forecast + IMD press release in parallel...", flush=True)
            fetches["mausamgram"] = pool.submit(_fetch_mausamgram)
        if not args.skip_imd:
            fetches["imd"] = pool.submit(_fetch_imd_context)

    if "mausamgram" in fetches:
        result["mausamgram"] = fetches["mausamgram"].result()
    if "imd" in fetches:
        result["imd_press_release"] = fetches["imd"].result()

    print("Step 2/3: Preparing answer...", flush=True)
    _print_human_summary(result)

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path("sessions") / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    output_path = Path(args.json_out) if args.json_out else session_dir / "forecast_data.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nStep 3/3: Verbose JSON saved to: {output_path.absolute()}", flush=True)


def _write_agent_log(log_dir: Path, entry: dict) -> None:
    """Append a structured log entry to the agent query log."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent_queries.log"
    with log_file.open("a", encoding="utf-8") as f:
        f.write("\n" + "=" * 70 + "\n")
        f.write(f"Timestamp : {entry['timestamp']}\n")
        f.write(f"Query     : {entry['query']}\n")
        f.write(f"Duration  : {entry['duration_sec']:.1f}s\n")
        f.write(f"Model     : {entry.get('model_path', 'N/A')}\n")
        if entry.get("tools_called"):
            f.write("\nTools Called:\n")
            for t in entry["tools_called"]:
                f.write(f"  [{t['order']}] {t['tool']}\n")
                f.write(f"       Input : {t['input']}\n")
                f.write(f"       Output: {t['output_preview']}\n")
        f.write(f"\nFinal Answer:\n{entry['answer']}\n")
        f.write("=" * 70 + "\n")
    return log_file


def _format_tool_output_as_answer(tool_calls: list, query: str) -> str:
    """
    Fallback: build a detailed, structured response directly from tool outputs
    when the LLM stalls or hits the iteration limit.  Handles the Mausamgram
    daily summary text returned by fetch_mausamgram_forecast_tool.
    """
    if not tool_calls:
        return ""

    # Find the last successful mausamgram tool call
    forecast_output = None
    for t in reversed(tool_calls):
        if t["tool"] == "fetch_mausamgram_forecast_tool" and t["output_preview"] != "(pending)":
            # The callback only stores the first 300 chars; get the full output via re-invoke
            forecast_output = t.get("_full_output") or t["output_preview"]
            break

    if not forecast_output or "5-day forecast" not in forecast_output:
        # Try any tool output that looks like a forecast
        for t in reversed(tool_calls):
            if "forecast" in t["output_preview"].lower() or "temp" in t["output_preview"].lower():
                forecast_output = t["output_preview"]
                break

    if not forecast_output:
        return ""

    # Parse the compact summary lines produced by _summarise_daily_records()
    lines = forecast_output.strip().split("\n")
    header = lines[0] if lines else "Forecast"
    day_lines = [l.strip() for l in lines[1:] if l.strip().startswith("20") or l.strip().startswith("  20")]

    if not day_lines:
        # Just return the raw output cleanly formatted
        return f"Based on data retrieved from Mausamgram:\n\n{forecast_output.strip()}"

    formatted = [f"Here is the detailed forecast ({header}):\n"]
    for dl in day_lines:
        formatted.append(f"  {dl}")

    # Summarise temperature range across all days
    import re
    all_tmin = re.findall(r"Temp\s+([\d.]+)-", forecast_output)
    all_tmax = re.findall(r"-([\d.]+)°C", forecast_output)
    rain_days = [dl for dl in day_lines if "rain" in dl.lower() and "no significant" not in dl.lower()]

    formatted.append("")
    if all_tmin and all_tmax:
        try:
            tmin_overall = min(float(v) for v in all_tmin)
            tmax_overall = max(float(v) for v in all_tmax)
            formatted.append(f"Overall temperature range: {tmin_overall}°C – {tmax_overall}°C")
        except ValueError:
            pass
    if rain_days:
        formatted.append(f"Rainfall expected on {len(rain_days)} of the forecast days.")
    else:
        formatted.append("No significant rainfall expected in the forecast period.")

    return "\n".join(formatted)


def run_legacy_react_agent(user_query, verbose: bool = False):
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain_community.llms import LlamaCpp
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.prompts import PromptTemplate

    class AgentEventLogger(BaseCallbackHandler):
        """Captures tool calls and their outputs for logging without printing chain noise."""
        def __init__(self):
            self.tool_calls: List[Dict[str, Any]] = []
            self._call_order = 0

        def on_tool_start(self, serialized, input_str, **kwargs):
            self._call_order += 1
            self.tool_calls.append({
                "order": self._call_order,
                "tool": serialized.get("name", "unknown"),
                "input": str(input_str)[:200],
                "output_preview": "(pending)",
            })

        def on_tool_end(self, output, **kwargs):
            if self.tool_calls:
                full = str(output)
                preview = full[:300].replace("\n", " ")
                self.tool_calls[-1]["output_preview"] = preview
                self.tool_calls[-1]["_full_output"] = full  # kept for Python-side fallback

    model_path = os.getenv("MODEL_PATH")
    if not model_path or not os.path.exists(model_path):
        raise ValueError("MODEL_PATH is not set correctly or does not exist.")

    llm = LlamaCpp(
        model_path=model_path,
        temperature=0.1,
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1024")),
        n_ctx=int(os.getenv("LLM_N_CTX", "32768")),
        n_gpu_layers=0,
        n_threads=int(os.getenv("LLM_N_THREADS", "32")),
        n_batch=512,
        verbose=verbose,
    )
    print("Successfully loaded local LLM.", flush=True)

    tools = [lookup_location, scrape_imd_press_release_urls, parse_imd_bulletins, fetch_mausamgram_forecast_tool]
    prompt_template = PromptTemplate.from_template("""
You are an expert meteorological assistant for India. You MUST use the tools provided to answer weather questions.
You must NEVER guess the weather. Always fetch it using a tool first.

Tools available:
{tools}

STRICT FORMAT RULES - follow these exactly or you will fail:
1. The "Action:" line must contain ONLY the bare tool name. NO parentheses, NO arguments, NO quotes.
   CORRECT:   Action: fetch_mausamgram_forecast_tool
   INCORRECT: Action: fetch_mausamgram_forecast_tool(input_data="...")
   INCORRECT: Action: fetch_mausamgram_forecast_tool("lat": 25.0)

2. ALL arguments go in "Action Input:" as a plain JSON object.
   CORRECT:   Action Input: {{"place": "Lucknow", "forecast_mode": "daily"}}
   INCORRECT: Action Input: {{}} (no input required)

3. You MUST use this EXACT format every time:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the tool name (BARE NAME ONLY, no parentheses!)
Action Input: a valid JSON object with the arguments
Observation: the result of the action
Thought: I now know the final answer based on the Observation.
Final Answer: the complete answer to the original question, including all relevant data from the Observation.

Available tool names: [{tool_names}]

Begin!

Question: {input}
{agent_scratchpad}
""")

    event_logger = AgentEventLogger()
    agent = create_react_agent(llm, tools, prompt_template)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        handle_parsing_errors=True,
        max_iterations=3,
        callbacks=[event_logger],
    )

    t_start = time.time()
    response = agent_executor.invoke({"input": user_query})
    duration = time.time() - t_start
    answer = response["output"]

    # If the model stalled, fall back to formatting the last tool output ourselves
    _STALL_PHRASES = ("agent stopped", "iteration limit", "time limit")
    if any(p in answer.lower() for p in _STALL_PHRASES):
        fallback = _format_tool_output_as_answer(event_logger.tool_calls, user_query)
        if fallback:
            answer = fallback

    # ── Terminal output ──────────────────────────────────────────────────────
    print("\n" + "=" * 60, flush=True)
    print("  AGENT RESPONSE", flush=True)
    print("=" * 60, flush=True)
    print(answer, flush=True)
    print("=" * 60, flush=True)

    if event_logger.tool_calls:
        print("\nData Sources:", flush=True)
        for t in event_logger.tool_calls:
            print(f"  [{t['order']}] {t['tool']}  ←  {t['input'][:80]}", flush=True)
    print(f"\nCompleted in {duration:.1f}s", flush=True)

    # ── Log file ─────────────────────────────────────────────────────────────
    log_dir = Path("logs")
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": user_query,
        "duration_sec": round(duration, 2),
        "model_path": model_path,
        "tools_called": event_logger.tool_calls,
        "answer": answer,
    }
    log_file = _write_agent_log(log_dir, log_entry)
    print(f"Full log appended to: {log_file.absolute()}", flush=True)


if __name__ == "__main__":
    args = _parse_args()

    # --agent flag takes priority; fall back to USE_REACT_AGENT env var for PBS compatibility
    use_agent = args.agent or os.getenv("USE_REACT_AGENT", "0") == "1"

    if use_agent:
        if args.query:
            user_query = args.query
        else:
            user_query = _prompt_user_query()
    else:
        user_query = "What is the latest weather forecast from the IMD?"

    print(f"\nUser Query: {user_query}", flush=True)
    print("--- Running Agent ---", flush=True)

    try:
        if use_agent:
            run_legacy_react_agent(user_query, verbose=args.verbose)
        else:
            run_direct_forecast(args)
    except Exception as exc:
        print(f"An error occurred while running the agent: {exc}", flush=True)
