import os
import argparse
import torch
from dotenv import load_dotenv
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# Load environment variables
load_dotenv()

def formatting_func(example):
    return example["output"]

def main():
    parser = argparse.ArgumentParser(description="Fine-tune an LLM on the agentic dataset using LoRA.")
    parser.add_argument(
        "--model", 
        type=str, 
        default="google/gemma-2b-it", 
        help="The HuggingFace model ID to fine-tune (e.g., HuggingFaceH4/zephyr-7b-beta, google/gemma-2b-it)"
    )
    parser.add_argument(
        "--dataset", 
        type=str, 
        default="finetuning_dataset.jsonl", 
        help="Path to the JSONL dataset."
    )
    parser.add_argument(
        "--output_dir", 
        type=str, 
        default="./agent-lora-adapter", 
        help="Directory to save the LoRA adapter weights."
    )
    parser.add_argument(
        "--max_seq_length",
        type=int,
        default=2048,
        help="Maximum sequence length for training examples. Longer examples will be truncated."
    )
    args = parser.parse_args()

    BASE_MODEL_NAME = args.model
    DATASET_PATH = args.dataset
    OUTPUT_DIR = args.output_dir

    print(f"========================================")
    print(f"Starting finetuning process")
    print(f"Model: {BASE_MODEL_NAME}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"========================================")

    # ====================
    # Load Model and Tokenizer
    # ====================
    print("Loading tokenizer and model...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_NAME,
        torch_dtype=torch.bfloat16,
        device_map="auto",
    )

    # ====================
    # LoRA Configuration
    # ====================
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ====================
    # Load and Format the Dataset
    # ====================
    print("Loading dataset...")
    dataset = load_dataset('json', data_files=DATASET_PATH)

    # ====================
    # Fine-Tuning Setup
    # ====================
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        num_train_epochs=3,
        logging_steps=10,
        report_to="none"
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset['train'],
        formatting_func=formatting_func,
        args=training_args,
        peft_config=lora_config,
        max_seq_length=args.max_seq_length,
    )

    # ====================
    # Start Training
    # ====================
    print("\nStarting fine-tuning...")
    trainer.train()

    # Save the final adapter weights
    trainer.save_model(OUTPUT_DIR)
    print(f"\nFine-tuning complete! Adapter saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    main()