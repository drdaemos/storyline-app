#!/usr/bin/env python3
"""Simple integration test for character database functionality."""

import os
import tempfile
from pathlib import Path


# Test the integration
def test_character_integration() -> None:
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Set environment for test database
        os.environ["DB_NAME"] = "test_characters.db"

        try:
            from src.character_loader import CharacterLoader
            from src.character_manager import CharacterManager

            # Create manager and loader
            manager = CharacterManager(characters_dir=f"{temp_dir}/characters", memory_dir=Path(temp_dir))
            loader = CharacterLoader(memory_dir=Path(temp_dir))

            # Test character data
            character_data = {"name": "Test Hero", "tagline": "Adventurer", "backstory": "A brave hero on a quest", "personality": "Bold and fearless", "appearance": "Tall with a sword"}

            # Create character file
            filename = manager.create_character_file(character_data)
            print(f"✓ Created character file: {filename}")

            # Load character from database
            character = loader.load_character(filename)
            print(f"✓ Loaded character: {character.name} - {character.tagline}")

            # List characters
            characters = loader.list_characters()
            print(f"✓ Characters in database: {characters}")

            # Test sync status
            status = manager.check_sync_status()
            print(f"✓ Sync status: {len(status['both_same'])} in sync")

            print("✓ All tests passed!")

        finally:
            # Clean up environment
            if "DB_NAME" in os.environ:
                del os.environ["DB_NAME"]


if __name__ == "__main__":
    test_character_integration()
