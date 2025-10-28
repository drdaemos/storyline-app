from .character import Character


def create_default_persona() -> Character:
    """
    Create a default persona character with minimal information.

    Returns:
        A Character instance with default "User" persona
    """
    return Character(
        name="User",
        tagline="Default user persona",
        backstory="A person participating in the conversation",
    )
