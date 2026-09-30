from auth.roles import (
    Roles,
    VALID_ROLES
)


def get_mock_user(
    user_id: str = "user_001",
    role: str = Roles.USER
):

    role = role.upper()

    if role not in VALID_ROLES:

        raise ValueError(
            f"Invalid role: {role}"
        )

    return {
        "user_id": user_id,
        "role": role
    }