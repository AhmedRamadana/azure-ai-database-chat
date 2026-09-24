from models.azure_gpt41_mini import ask_mini


response = ask_mini(
    "Say hello and confirm that GPT-4.1 mini is connected."
)

print(response)