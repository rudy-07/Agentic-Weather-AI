"""
fix_dataset.py — Rewrites finetuning_dataset.jsonl from scratch with:
  - Correct tool names (scrape_imd_press_release_urls, parse_imd_bulletins)
  - 10 new examples using fetch_mausamgram_forecast_tool

Run once from the agentic_ai directory:
    python fix_dataset.py
"""
import json
from pathlib import Path

OUTPUT = Path("finetuning_dataset.jsonl")

PDF_URL = "https://internal.imd.gov.in/press_release/20250916_pr_4302.pdf"

def _make(instruction, output):
    return {"instruction": instruction, "output": output}

def _imd(instruction, thought1, action2_input, observation, thought2, answer):
    """Helper for the standard 2-tool IMD bulletin pattern."""
    return _make(instruction, (
        f"Thought: {thought1}\n"
        f"Action: scrape_imd_press_release_urls\n"
        f"Action Input: {{}}\n"
        f"Observation: {PDF_URL}\n"
        f"Thought: I have the URL. {action2_input}\n"
        f"Action: parse_imd_bulletins\n"
        f'Action Input: {{"urls": ["{PDF_URL}"]}}\n'
        f"Observation: {observation}\n"
        f"Thought: {thought2}\n"
        f"Final Answer: {answer}"
    ))

# All 29 original examples with corrected tool names
original_29 = [
    _imd(
        "What is the latest monsoon update for Maharashtra?",
        "The user wants to know about the monsoon in a specific location. I need to get the latest IMD bulletin and then find information related to Maharashtra.",
        "I will now parse the bulletin to find the monsoon-related information for Maharashtra.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Southwest Monsoon has further advanced into Maharashtra. Widespread rainfall is expected."}]',
        "I have the information. The monsoon has advanced into Maharashtra and is bringing rainfall.",
        "The Southwest Monsoon has advanced into Maharashtra, and widespread rainfall is expected in the region."
    ),
    _imd(
        "Are there any current flood warnings for the state of Assam?",
        "The user is asking about a specific type of warning for Assam. I need to find the latest bulletin and check for flood warnings.",
        "I will now parse the document to check for any flood warnings or related advisories for Assam.",
        '[{"document_type": "Daily Forecast Bulletin", "warning": "Flood warning issued for parts of Assam due to heavy rainfall."}]',
        "The bulletin confirms a flood warning for Assam.",
        "Yes, a flood warning has been issued for parts of Assam due to heavy rainfall, as per the latest IMD bulletin."
    ),
    _imd(
        "What is the agricultural advisory for farmers in Bihar?",
        "The user wants to know about agricultural advisories for a specific state. I need to find the latest bulletin and extract the relevant information for Bihar.",
        "I will parse the bulletin to find the agricultural advisories section and locate the information for Bihar.",
        '[{"document_type": "Daily Forecast Bulletin", "action_suggested": "In Bihar, ensure proper drainage of excess rainwater from standing crops such as maize, finger millet and vegetables."}]',
        "I have found the specific advisory for Bihar.",
        "Farmers in Bihar are advised to ensure proper drainage of excess rainwater from their fields, especially for crops like maize, finger millet, and vegetables."
    ),
    _imd(
        "What is the forecast for tomorrow's temperature in Kolkata?",
        "The user is asking for a temperature forecast for a specific city. I will search the latest bulletin for this information.",
        "I will parse the PDF to find the temperature forecast for Kolkata.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Moderate rainfall expected in Kolkata region. Temperature (Max/Min): 31.2°C/26.5°C."}]',
        "I found the temperature data in the bulletin. The forecast shows 31.2°C max.",
        "The maximum temperature forecast for Kolkata is 31.2°C, and moderate rainfall is also expected."
    ),
    _imd(
        "Are there any current heatwave warnings for Rajasthan?",
        "The user is asking about heatwave warnings for Rajasthan. I need to get the latest IMD bulletin and check for this specific alert.",
        "I will parse the bulletin and look for any mention of a 'heatwave' in the warnings or forecast sections.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "This is the latest press release about rainfall and flash floods. There is no mention of heatwaves in Rajasthan."}]',
        "I have searched the document and no heatwave warnings were mentioned for Rajasthan in this bulletin.",
        "There are no current heatwave warnings for Rajasthan mentioned in the latest IMD bulletin. The report focuses on rainfall and flood risk."
    ),
    _make(
        "What is a 'Western Disturbance' and how does it affect weather in North India?",
        "Thought: The user is asking for a definition and a general explanation, not for a specific weather update. This is a knowledge-based question that does not require using my tools.\nFinal Answer: A 'Western Disturbance' is an extratropical storm originating in the Mediterranean region. During winter, it brings crucial moisture to Northwest India, causing rain in the plains and heavy snowfall in the Himalayas. This precipitation is vital for Rabi crops like wheat."
    ),
    _imd(
        "What are the suggested actions for the public in areas with a high risk of flash floods?",
        "The user is asking for public advisories related to flash floods. I need to get the latest bulletin and check the 'Action Suggested' section.",
        "I will parse the PDF and extract the 'Action Suggested' section, focusing on flash floods.",
        '[{"document_type": "Daily Forecast Bulletin", "action_suggested": "Avoid going to areas that face waterlogging problems often. Avoid staying in vulnerable structures."}]',
        "I have the public advisory information. I can now provide the final answer.",
        "The public is advised to avoid areas that are prone to waterlogging and to stay away from vulnerable structures, especially in regions with a high flash flood risk."
    ),
    _make(
        "What is the advisory for livestock owners during a severe heatwave in Rajasthan?",
        "Thought: The user is asking for a specific advisory. The latest bulletin is about rain, so I will have to provide a general advisory based on my knowledge base.\nFinal Answer: During a severe heatwave, livestock owners are advised to move animals to shaded areas during the day, provide ample clean drinking water, and avoid grazing during peak sun hours (11 AM to 4 PM)."
    ),
    _make(
        "How will a delayed monsoon affect power generation in the southern states?",
        "Thought: The user is asking for an inference based on a hypothetical scenario. This is an advanced question that requires a synthesis of meteorological and infrastructural knowledge. This does not require a tool call.\nFinal Answer: A delayed monsoon in southern states like Karnataka, Kerala, and Tamil Nadu will lead to lower water levels in the major reservoirs. This directly impacts hydroelectric power generation, which is a significant part of the region's energy mix, potentially leading to a power deficit and increased reliance on other energy sources."
    ),
    _imd(
        "Which district in Kerala received the most rainfall in the past 24 hours?",
        "The user is asking for specific rainfall data from the latest report. I need to find the latest IMD bulletin and then find the rainfall data for Kerala.",
        "I will now parse the PDF to find the rainfall data for Kerala and identify the district with the most rainfall.",
        '[{"document_type": "Daily Forecast Bulletin", "rainfall_warnings": "Kerala & Mahe: Ponnani (dist Malappuram) 10cm, Vellanikkara (dist Thrissur) 8cm."}]',
        "I have the rainfall data. Based on my analysis, Ponnani in the Malappuram district received 10cm rainfall, the highest listed in the Kerala section.",
        "Based on the latest report, the Ponnani district in Kerala received the most rainfall in the past 24 hours with 10cm."
    ),
    _imd(
        "Is it safe for fishermen to go to the sea along the Gujarat coast?",
        "The user is asking for a specific advisory for fishermen in Gujarat. I need to find the latest IMD bulletin and check for any warnings.",
        "I will now parse the bulletin and look for the 'Fishermen Warning' section, specifically for the Gujarat coast.",
        '[{"document_type": "Daily Forecast Bulletin", "warning": "Fishermen Warning: Squally weather with wind speed reaching 45-55 kmph is likely along and off Gujarat coast. Fishermen are advised not to venture into the sea."}]',
        "I have found a clear advisory for fishermen in Gujarat.",
        "No, it is not safe. The IMD has issued a warning for the Gujarat coast due to squally weather with wind speeds expected to reach 45-55 kmph. Fishermen are advised not to venture into the sea."
    ),
    _imd(
        "What is the latest update on the low-pressure area over the Bay of Bengal?",
        "The user is asking about a specific weather system. I need to check the latest bulletin for information on cyclonic circulations or low-pressure areas.",
        "I will parse the document, looking for the 'Chief synoptic conditions' to get details on the low-pressure area.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "A low pressure area lies over Westcentral Bay of Bengal. It is likely to become more marked and move west-northwestwards during the next 48 hours."}]',
        "I have found the current status and forecast for the low-pressure area.",
        "A low-pressure area is currently located over the Westcentral Bay of Bengal. It is expected to intensify and move in a west-northwestward direction over the next 48 hours."
    ),
    _imd(
        "How has the monsoon performed in the Marathwada region so far?",
        "The user wants to know about the cumulative monsoon performance in a specific sub-division. I need to find the table with rainfall statistics in the latest bulletin.",
        "I will parse the bulletin to find the table showing sub-division wise rainfall distribution.",
        '[{"document_type": "Weekly Rainfall Summary", "summary_data": [{"region": "Marathwada", "actual_mm_week": "580", "normal_mm_week": "725", "departure_percent_week": "-20%"}]}]',
        "I have found the rainfall departure data for Marathwada in a table.",
        "The Marathwada region has received 580 mm of rainfall against a normal of 725 mm, resulting in a 20% deficit for the season so far."
    ),
    _imd(
        "What is the visibility forecast for Delhi in the early morning?",
        "The user is asking about visibility, which is often related to fog, for a specific city. I should check the city-specific forecast section of the IMD bulletin.",
        "I will parse the bulletin and search for the forecast for Delhi, looking for terms like 'visibility' or 'fog'.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Forecast for Delhi: Mainly clear sky. Shallow to moderate fog in the morning. Visibility likely to be 500-800 meters."}]',
        "I have found the specific visibility forecast for Delhi.",
        "For Delhi, shallow to moderate fog is expected in the early morning, with visibility likely to be between 500 and 800 meters."
    ),
    _imd(
        "What are the expected wind speeds along the coast of Tamil Nadu tomorrow?",
        "The user wants a wind speed forecast for a specific coastal area. I need to check the weather bulletin for marine or coastal forecasts.",
        "I will parse the bulletin to find wind forecasts, particularly for the Tamil Nadu coast.",
        '[{"document_type": "Daily Forecast Bulletin", "warning": "Strong surface winds of 40-50 kmph likely to prevail over Tamil Nadu coast and Gulf of Mannar."}]',
        "I have found the wind speed forecast for the specified region.",
        "Strong surface winds of 40-50 kmph are expected along the coast of Tamil Nadu and in the Gulf of Mannar tomorrow."
    ),
    _imd(
        "Has the Southwest Monsoon started withdrawing from Northwest India?",
        "The user is asking about the status of the monsoon withdrawal, which is a major event covered in the bulletin's summary.",
        "I will parse the bulletin and look for keywords like 'withdrawal', 'Southwest Monsoon', and 'Northwest India' in the main text.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Conditions are becoming favourable for commencement of withdrawal of Southwest Monsoon from parts of West Rajasthan in next 2-3 days."}]',
        "I have found the current status regarding the monsoon withdrawal.",
        "The Southwest Monsoon has not yet started withdrawing, but conditions are becoming favorable for its withdrawal from parts of West Rajasthan within the next 2-3 days."
    ),
    _imd(
        "What are the main weather systems currently affecting India?",
        "The user wants a general overview of the weather systems. This information is typically found in the 'Chief synoptic conditions' section of the IMD report.",
        "I will parse the bulletin and extract the key points from the synoptic conditions summary.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Chief synoptic conditions: 1) The monsoon trough at mean sea level runs from Punjab to northeast Bay of Bengal. 2) A cyclonic circulation lies over central Madhya Pradesh. 3) A low pressure area lies over Westcentral Bay of Bengal."}]',
        "I have extracted the list of the main weather systems.",
        "The main weather systems currently affecting India are: the monsoon trough running from Punjab to the northeast Bay of Bengal, a cyclonic circulation over central Madhya Pradesh, and a low-pressure area over the Westcentral Bay of Bengal."
    ),
    _imd(
        "Which states are under a heavy rainfall orange alert for today?",
        "The user is asking for specific information about heavy rainfall warnings, identified by the 'orange alert' color code. I need to find the warnings table in the bulletin.",
        "I will parse the bulletin to locate the table detailing weather warnings and identify the states listed under the 'Orange' category.",
        '[{"document_type": "Daily Forecast Bulletin", "rainfall_warnings": "Orange Alert: Odisha, Chhattisgarh, East Madhya Pradesh. Yellow Alert: Konkan & Goa."}]',
        "I have successfully identified the states that have an orange alert for heavy rainfall.",
        "According to the latest IMD bulletin, the states under an orange alert for heavy rainfall today are Odisha, Chhattisgarh, and East Madhya Pradesh."
    ),
    _imd(
        "Is there a thunderstorm and lightning warning for Odisha?",
        "The user is asking about a specific type of warning (thunderstorm with lightning) for a particular state. I need to check the detailed forecast and warnings section of the bulletin for Odisha.",
        "I will now parse the bulletin and search for any text that mentions 'thunderstorm', 'lightning', and 'Odisha'.",
        '[{"document_type": "Daily Forecast Bulletin", "warning": "Heavy to very heavy rainfall with thunderstorm & lightning very likely at isolated places over Odisha."}]',
        "The bulletin confirms a thunderstorm and lightning warning for Odisha.",
        "Yes, the latest IMD report indicates that thunderstorms with lightning are very likely at isolated places over Odisha, along with heavy to very heavy rainfall."
    ),
    _make(
        "What does an 'Orange Alert' from the IMD signify?",
        "Thought: The user is asking for the definition of a term used by the IMD. This is a general knowledge question and does not require accessing the latest bulletin.\nFinal Answer: An 'Orange Alert' from the India Meteorological Department (IMD) signifies a warning to 'Be Prepared'. It indicates that weather conditions have the potential to worsen and could cause disruptions to daily life, such as transportation and power supply. Authorities are advised to be ready to take necessary action."
    ),
    _imd(
        "Are there any dust storm warnings for Meghalaya?",
        "The user is asking about a specific warning for a state where it is highly unlikely to occur. I will search the latest bulletin to confirm its absence.",
        "I will now parse the bulletin and search for any mention of 'dust storm' in relation to 'Meghalaya' within the warnings section.",
        '[{"document_type": "Daily Forecast Bulletin", "warning": "Heavy rainfall warning for Meghalaya. No dust storm warnings mentioned."}]',
        "I have confirmed that the bulletin contains a heavy rainfall warning but no dust storm warning for Meghalaya.",
        "The latest IMD bulletin does not contain any information about dust storm warnings for Meghalaya. The current active warning for the state is for heavy rainfall."
    ),
    _imd(
        "What is the rainfall forecast for Aurangabad?",
        "The user has mentioned 'Aurangabad', which exists in two different states (Maharashtra and Bihar). I must check the bulletin to see if it provides a forecast for either.",
        "I will parse the bulletin to find any mention of 'Aurangabad'.",
        '[{"document_type": "Daily Forecast Bulletin", "rainfall_warnings": "Marathwada sub-division: Aurangabad - 4cm rainfall in past 24 hours."}]',
        "The bulletin mentions rainfall data for Aurangabad in the Marathwada sub-division (Maharashtra), but not a future forecast.",
        "The latest bulletin provides rainfall data for Aurangabad, Maharashtra (in the Marathwada sub-division), which recorded 4cm of rain in the past 24 hours. However, a specific future forecast for the city is not mentioned in the report."
    ),
    _imd(
        "What will the temperature be in Chennai next month?",
        "The user is asking for a long-range forecast (a month ahead), which is typically beyond the scope of a daily weather bulletin. I need to check the forecast period covered by the bulletin.",
        "I will parse the bulletin to identify the time range of its forecasts.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Forecast and warnings for next 5 days."}]',
        "The bulletin explicitly states that its forecast horizon is 5 days. I cannot fulfill the user's request.",
        "I cannot provide a temperature forecast for next month. The latest IMD bulletin only contains detailed weather forecasts for the next 5 days."
    ),
    _make(
        "How much rain did Mumbai get last Tuesday?",
        "Thought: The user is asking for historical weather data for a specific day in the past. My primary data source is the latest daily bulletin, which typically contains data for the 'last 24 hours' only. This query is outside the scope of my tools.\nFinal Answer: I cannot answer that question. My function is to provide information from the latest daily weather report, which includes data for the last 24 hours but does not serve as a historical weather archive. For historical data, you may need to consult the IMD's archival records on their official website."
    ),
    _make(
        "What is the current sea surface temperature anomaly in the Nino 3.4 region?",
        "Thought: The user is asking for a highly specific and technical climatological parameter. This type of data is not typically included in a daily public weather press release focused on short-term forecasts for India.\nFinal Answer: That is a very specific query about a climatological index. The daily IMD weather bulletin focuses on short-to-medium range operational forecasts and warnings for India and does not contain detailed information on global climate indices like the Nino 3.4 SST anomaly."
    ),
    _imd(
        "Is the heavy rain warning for Odisha related to the low-pressure area in the Bay of Bengal?",
        "The user is asking to connect a cause (a weather system) with an effect (a specific warning). This requires synthesizing information from two different parts of the bulletin.",
        "I will parse the bulletin to find mentions of the low-pressure area and the warnings for Odisha to see if a link is explicitly stated.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "A low pressure area lies over Westcentral Bay of Bengal. Under its influence, widespread rainfall with isolated heavy to very heavy falls is likely over Odisha for the next 3 days. Orange alert issued."}]',
        "The bulletin explicitly connects the low-pressure system to the heavy rainfall warning in Odisha.",
        "Yes, absolutely. The latest bulletin states that the heavy rainfall warning and orange alert for Odisha are issued under the influence of the low-pressure area currently located over the Westcentral Bay of Bengal."
    ),
    _make(
        "What are the show timings for the new movie in PVR Cinemas?",
        "Thought: The user is asking a question that is completely unrelated to weather or the India Meteorological Department. My function is to provide weather information. I must decline this request.\nFinal Answer: I am an AI assistant designed to provide weather updates and information from IMD bulletins. I do not have access to information about movie show timings."
    ),
    _imd(
        "What's the weather like in Chennai tonight?",
        "The user is asking for a forecast with a vague time reference, 'tonight'. I need to find the detailed city forecast for Chennai.",
        "I will parse the bulletin and look for the city-specific forecast table or text for Chennai.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Chennai: Sky partly cloudy. Light rain or thundershowers may occur in some areas towards night or early morning. Max Temp: 34°C, Min Temp: 26°C."}]',
        "I have found the forecast. I can describe the night conditions.",
        "For Chennai tonight, the sky is expected to be partly cloudy, and light rain or thundershowers may occur in some areas. The minimum temperature is forecast to be around 26°C."
    ),
    _imd(
        "I heard the monsoon is weakening, so why is there a flood warning for Assam?",
        "The user is presenting an apparent contradiction. I need to carefully check the bulletin for both the overall monsoon status and the specific regional forecast for Northeast India.",
        "I will parse the bulletin to find the overall monsoon synopsis and the specific forecast details for Assam.",
        '[{"document_type": "Daily Forecast Bulletin", "forecast": "Southwest Monsoon has been subdued over central and peninsular India. However, strong moist southerly winds from the Bay of Bengal continue to feed moisture into Northeast India, causing heavy rainfall. Flood warning issued for parts of Assam."}]',
        "The bulletin addresses this directly. The monsoon is weak in some parts but a different local mechanism is causing heavy rain in the Northeast.",
        "That's a great question. While the bulletin notes that the monsoon has become subdued over central and peninsular India, a different weather pattern is impacting the Northeast. Strong moist winds from the Bay of Bengal are causing persistent heavy rainfall specifically over that region, which has led to the flood warning for parts of Assam."
    ),
    _make(
        "Can you show me the satellite image of the cloud cover over India?",
        "Thought: The user is requesting visual data (an image). As a text-based model, I cannot generate or display images. I must inform the user about this limitation.\nFinal Answer: As a text-based AI assistant, I am unable to display images or maps, including satellite imagery. However, I can describe the cloud cover and major weather systems based on the text descriptions in the IMD bulletin. For real-time satellite images, I would recommend visiting the official IMD website."
    ),
]

# 10 new examples using fetch_mausamgram_forecast_tool
new_10 = [
    _make(
        "Which days will it rain in Prayagraj next week?",
        "Thought: The user wants a daily rain forecast for Prayagraj. I will fetch the Mausamgram daily forecast using the place name.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Prayagraj", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Prayagraj:\n"
        "  2026-06-11: Light Rain (1.2mm), Temp 34-43°C, Cloud 46%, Wind South-South Easterly 3.7m/s.\n"
        "  2026-06-12: Light Rain (2.6mm), Temp 32-44°C, Cloud 44%, Wind East-North Easterly 2.7m/s.\n"
        "  2026-06-13: Light Rain (1.6mm), Temp 32-42°C, Cloud 51%, Wind South Westerly 2.6m/s.\n"
        "  2026-06-14: Light Rain (1.4mm), Temp 34-44°C, Cloud 25%, Wind East-North Easterly 2.8m/s.\n"
        "  2026-06-15: No significant rain (0.9mm), Temp 33-44°C, Cloud 25%, Wind West-South Westerly.\n"
        "Thought: Based on the forecast, all five days show some rain, with the heaviest on June 12.\n"
        "Final Answer: Rain is expected every day next week in Prayagraj. The heaviest rainfall (2.6mm) is forecast for June 12. June 15 will have the least rain at only 0.9mm."
    ),
    _make(
        "What is the temperature forecast for Mumbai tomorrow?",
        "Thought: The user wants the temperature for Mumbai tomorrow. I'll use the daily Mausamgram forecast.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Mumbai", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Mumbai:\n"
        "  2026-06-11: Light Rain (5.1mm), Temp 26-31°C, Cloud 85%, Wind South Westerly 6.2m/s.\n"
        "  2026-06-12: Moderate Rain (12.4mm), Temp 25-30°C, Cloud 90%, Wind South Westerly 7.1m/s.\n"
        "Thought: Tomorrow is June 12. The min temp is 25°C and max is 30°C.\n"
        "Final Answer: Tomorrow in Mumbai, the minimum temperature will be around 25°C and the maximum will be 30°C, with moderate rain expected."
    ),
    _make(
        "Will there be wind in Chennai today?",
        "Thought: The user wants wind information for Chennai today. I will fetch the daily forecast.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Chennai", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Chennai:\n"
        "  2026-06-11: Light Rain (3.2mm), Temp 28-35°C, Cloud 70%, Wind South Westerly 5.1m/s. Partly Cloudy.\n"
        "Thought: Today is June 11. Wind speed is 5.1 m/s from the South-West direction.\n"
        "Final Answer: Yes, winds of approximately 5.1 m/s (about 18 km/h) from the South-West direction are expected in Chennai today."
    ),
    _make(
        "Get me the hourly forecast for Delhi for the next day.",
        "Thought: The user wants an hourly forecast for Delhi. I will use the 1hr forecast mode.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Delhi", "forecast_mode": "1hr"}\n'
        "Observation: 1hr forecast for Delhi (36 time-steps):\n"
        "  2026-06-11T06:00: rain=0mm, temp=28°C\n"
        "  2026-06-11T07:00: rain=0mm, temp=29°C\n"
        "  2026-06-11T08:00: rain=0.1mm, temp=31°C\n"
        "  ... 33 more time-steps omitted.\n"
        "Thought: I have the hourly data for Delhi. The morning is dry with light rain expected by 8am.\n"
        "Final Answer: Delhi's hourly forecast shows a dry early morning (6-7am at 28-29°C) with very light rain of 0.1mm possible by 8am."
    ),
    _make(
        "Is there a heatwave risk in Nagpur this week based on the forecast?",
        "Thought: The user is asking about heatwave risk in Nagpur. A heatwave is typically when max temp exceeds 40°C. I'll fetch the daily forecast.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Nagpur", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Nagpur:\n"
        "  2026-06-11: No significant rain (0.0mm), Temp 29-44°C, Cloud 10%, Wind South Easterly 2.1m/s. Mainly Clear Sky.\n"
        "  2026-06-12: No significant rain (0.0mm), Temp 28-45°C, Cloud 8%, Wind South Easterly 1.8m/s. Mainly Clear Sky.\n"
        "  2026-06-13: No significant rain (0.1mm), Temp 28-43°C, Cloud 15%, Wind South Westerly 2.5m/s.\n"
        "  2026-06-14: Light Rain (0.5mm), Temp 27-41°C, Cloud 30%, Wind South Westerly 3.1m/s.\n"
        "  2026-06-15: Light Rain (1.1mm), Temp 26-39°C, Cloud 45%, Wind South Westerly 3.8m/s.\n"
        "Thought: Temperatures exceed 40°C on 4 out of 5 days, peaking at 44-45°C on Jun 11-12. This is well within heatwave territory.\n"
        "Final Answer: Yes, there is a significant heatwave risk in Nagpur this week. Maximum temperatures are forecast to reach 44°C on June 11 and 45°C on June 12. Conditions ease toward the weekend with some cloud and light rain."
    ),
    _make(
        "Compare the rainfall in Bengaluru vs Hyderabad for the next 5 days.",
        "Thought: I need to fetch forecasts for two cities and compare them. I'll do Bengaluru first.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Bengaluru", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Bengaluru:\n"
        "  2026-06-11: Light Rain (4.2mm), Temp 20-28°C\n"
        "  2026-06-12: Moderate Rain (8.5mm), Temp 19-27°C\n"
        "  2026-06-13: Moderate Rain (10.1mm), Temp 20-27°C\n"
        "  2026-06-14: Light Rain (5.3mm), Temp 20-28°C\n"
        "  2026-06-15: Light Rain (3.9mm), Temp 21-29°C\n"
        "Thought: Now I'll get Hyderabad's forecast.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Hyderabad", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Hyderabad:\n"
        "  2026-06-11: No Rain (0.0mm), Temp 26-38°C\n"
        "  2026-06-12: Light Rain (1.1mm), Temp 25-37°C\n"
        "  2026-06-13: Light Rain (2.3mm), Temp 25-36°C\n"
        "  2026-06-14: Light Rain (1.5mm), Temp 26-37°C\n"
        "  2026-06-15: Light Rain (0.8mm), Temp 27-38°C\n"
        "Thought: Bengaluru will receive ~32mm total vs Hyderabad ~5.7mm. Bengaluru is also much cooler.\n"
        "Final Answer: Bengaluru will be significantly wetter (~32mm total, peaking at 10mm on June 13) vs Hyderabad (~5.7mm). Bengaluru temperatures (19-28°C) will also be considerably cooler than Hyderabad (25-38°C)."
    ),
    _make(
        "What is the cloud cover forecast for Kolkata tomorrow?",
        "Thought: The user wants cloud cover for Kolkata. The Mausamgram daily forecast includes this field.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Kolkata", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Kolkata:\n"
        "  2026-06-11: Light Rain (2.1mm), Temp 28-34°C, Cloud 75%, Wind South Westerly 4.3m/s. Mostly Cloudy.\n"
        "  2026-06-12: Moderate Rain (6.8mm), Temp 26-32°C, Cloud 88%, Wind South Westerly 5.2m/s. Overcast.\n"
        "Thought: Tomorrow is June 12. Cloud cover is 88%, described as overcast.\n"
        "Final Answer: Tomorrow in Kolkata, cloud cover will be very heavy at 88% — the sky will be largely overcast with moderate rain of about 6.8mm expected."
    ),
    _make(
        "Is it going to be sunny in Jaipur this weekend?",
        "Thought: The user wants to know if it will be sunny this weekend in Jaipur. I need the 5-day daily forecast.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Jaipur", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Jaipur:\n"
        "  2026-06-11: No significant rain (0.0mm), Temp 30-42°C, Cloud 12%, Wind South Easterly 2.8m/s. Mainly Clear Sky.\n"
        "  2026-06-12: No significant rain (0.1mm), Temp 29-41°C, Cloud 18%, Wind South Easterly 2.5m/s. Mainly Clear Sky.\n"
        "  2026-06-13: No significant rain (0.2mm), Temp 29-40°C, Cloud 22%, Wind South Westerly 3.1m/s. Mainly Clear Sky.\n"
        "  2026-06-14: Light Rain (0.8mm), Temp 28-38°C, Cloud 35%, Wind South Westerly 4.2m/s. Partly Cloudy.\n"
        "  2026-06-15: Light Rain (1.5mm), Temp 27-36°C, Cloud 55%, Wind South Westerly 5.1m/s. Partly Cloudy.\n"
        "Thought: The weekend (Jun 14-15) shows partly cloudy skies with some light rain, cloud cover 35-55%. Not fully sunny.\n"
        "Final Answer: The weekend in Jaipur will not be fully sunny. Saturday (June 14) will be partly cloudy (35% cloud) with light rain (0.8mm). Sunday (June 15) will be more overcast (55% cloud) with 1.5mm rain possible."
    ),
    _make(
        "What is the 3-hour forecast for Pune for the next few hours?",
        "Thought: The user wants a short-term 3-hour interval forecast for Pune.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Pune", "forecast_mode": "3hr"}\n'
        "Observation: 3hr forecast for Pune (40 time-steps):\n"
        "  2026-06-11T06:00: rain=0mm, temp=22°C\n"
        "  2026-06-11T09:00: rain=0mm, temp=26°C\n"
        "  2026-06-11T12:00: rain=1.2mm, temp=30°C\n"
        "  2026-06-11T15:00: rain=2.5mm, temp=29°C\n"
        "  2026-06-11T18:00: rain=3.1mm, temp=27°C\n"
        "  2026-06-11T21:00: rain=1.0mm, temp=24°C\n"
        "  ... 34 more time-steps omitted.\n"
        "Thought: The morning starts dry, then rain builds from noon onwards, peaking in the evening.\n"
        "Final Answer: For Pune today, the morning is dry (no rain until noon, 22-26°C). Rain begins around noon (1.2mm at 30°C) and peaks in the evening at 3.1mm at 6pm."
    ),
    _make(
        "Is it safe to travel from Delhi to Agra tomorrow by road given the weather?",
        "Thought: The user wants weather-based travel advice. I need the daily forecast for both Delhi and Agra.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Delhi", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Delhi:\n"
        "  2026-06-12: No Rain (0.1mm), Temp 27-40°C, Cloud 15%, Wind South Easterly 2.8m/s. Mainly Clear Sky.\n"
        "Thought: Delhi looks clear tomorrow. Let me check Agra.\n"
        "Action: fetch_mausamgram_forecast_tool\n"
        'Action Input: {"place": "Agra", "forecast_mode": "daily"}\n'
        "Observation: 5-day forecast for Agra:\n"
        "  2026-06-12: No Rain (0.1mm), Temp 28-42°C, Cloud 12%, Wind South Easterly 2.3m/s. Mainly Clear Sky.\n"
        "Thought: Both cities will be clear tomorrow with no rain. Main concern is high temperatures of 40-42°C.\n"
        "Final Answer: Weather conditions along the Delhi-Agra route look safe for road travel tomorrow. Both cities forecast mainly clear skies with no significant rainfall. However, temperatures will be very high (40-42°C), so carry plenty of water and avoid travelling during peak afternoon hours (12pm-4pm)."
    ),
]

all_examples = original_29 + new_10
with OUTPUT.open("w", encoding="utf-8") as f:
    for ex in all_examples:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

print(f"Done! Written {len(all_examples)} examples ({len(original_29)} original + {len(new_10)} new) to {OUTPUT}")
