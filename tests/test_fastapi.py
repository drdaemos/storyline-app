#!/usr/bin/env python3
"""
Test script for the FastAPI server.
This script demonstrates how to interact with the storyline API endpoints.
"""

import json

import requests


def test_api_endpoints() -> None:
    """Test basic API endpoints."""
    base_url = "http://localhost:8000"

    print("🚀 Testing Storyline API endpoints...")

    try:
        # Test root endpoint
        print("\n1. Testing root endpoint...")
        response = requests.get(f"{base_url}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

        # Test characters endpoint
        print("\n2. Testing characters list...")
        response = requests.get(f"{base_url}/characters")
        print(f"Status: {response.status_code}")
        characters = response.json()
        print(f"Available characters: {characters}")

        if not characters:
            print("❌ No characters found. Make sure you have character files in the characters/ directory.")
            return

        # Test character info
        character_name = characters[0]
        print(f"\n3. Testing character info for '{character_name}'...")
        response = requests.get(f"{base_url}/characters/{character_name}")
        print(f"Status: {response.status_code}")
        print(f"Character info: {json.dumps(response.json(), indent=2)}")

        # Test sessions endpoint
        print("\n4. Testing sessions list...")
        response = requests.get(f"{base_url}/sessions")
        print(f"Status: {response.status_code}")
        print(f"Active sessions: {response.json()}")

        print("\n✅ Basic API endpoints test completed!")

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API server. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error testing API endpoints: {e}")


def test_streaming_interaction() -> None:
    """Test the streaming interaction endpoint."""
    base_url = "http://localhost:8000"

    print("\n🌊 Testing streaming interaction...")

    try:
        # First, get available characters
        response = requests.get(f"{base_url}/characters")
        characters = response.json()

        if not characters:
            print("❌ No characters available for testing")
            return

        character_name = characters[0]
        print(f"Testing with character: {character_name}")

        # Test streaming interaction
        interaction_data = {"character_name": character_name, "user_message": "Hello! How are you today?", "session_id": "manual-test-session"}

        print("\nSending interaction request...")
        print(f"Request data: {json.dumps(interaction_data, indent=2)}")

        # Make streaming request
        response = requests.post(f"{base_url}/interact", json=interaction_data, stream=True, timeout=30)

        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        if response.status_code != 200:
            print(f"❌ Error: {response.text}")
            return

        print("\n📡 Streaming response:")
        print("-" * 50)

        full_response = ""
        session_id = None

        for line in response.iter_lines(decode_unicode=True):
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                try:
                    data = json.loads(data_str)

                    if data["type"] == "session":
                        session_id = data["session_id"]
                        print(f"Session ID: {session_id}")

                    elif data["type"] == "chunk":
                        content = data["content"]
                        print(content, end="", flush=True)
                        full_response += content

                    elif data["type"] == "complete":
                        print("\n" + "-" * 50)
                        print("✅ Response completed!")
                        print(f"Total message count: {data['message_count']}")
                        print(f"Session ID: {session_id}")
                        break

                    elif data["type"] == "error":
                        print(f"\n❌ Error: {data['error']}")
                        break

                except json.JSONDecodeError:
                    print(f"Invalid JSON: {data_str}")

        # Test session management
        if session_id:
            print("\n🗂️  Testing session management...")

            # List sessions
            response = requests.get(f"{base_url}/sessions")
            sessions = response.json()
            print(f"Active sessions: {len(sessions)}")

            # Clear session
            response = requests.delete(f"{base_url}/sessions/{session_id}")
            if response.status_code == 200:
                print(f"✅ Session {session_id} cleared successfully")
            else:
                print(f"❌ Failed to clear session: {response.text}")

        print("\n✅ Streaming interaction test completed!")

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API server. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error testing streaming interaction: {e}")


def main() -> None:
    """Run all tests."""
    print("🧪 Storyline API Test Suite")
    print("=" * 50)

    # Test basic endpoints
    test_api_endpoints()

    # Test streaming interaction
    test_streaming_interaction()

    print("\n🎉 All tests completed!")


if __name__ == "__main__":
    main()
