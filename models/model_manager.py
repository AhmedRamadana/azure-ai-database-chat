from models.azure_gpt41_nano import ask_nano
from models.azure_gpt41_mini import ask_mini


def get_model(model_name: str):

    if model_name == "nano":
        return ask_nano

    elif model_name == "mini":
        return ask_mini

    else:
        raise ValueError(
            f"Unknown model: {model_name}"
        )