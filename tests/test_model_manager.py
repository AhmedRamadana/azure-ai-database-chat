from models.model_manager import get_model


model = get_model("mini")

response = model(
    "Say hello and tell me which model you are."
)

print(response)