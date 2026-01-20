"""
Test Anthropic API Key

Quick script to verify your API key is valid and working.
"""

import sys
from anthropic import Anthropic
from anthropic import APIError, AuthenticationError


def test_api_key(api_key: str):
    """
    Test if an API key is valid.

    Args:
        api_key: Anthropic API key to test

    Returns:
        True if valid, False otherwise
    """
    print("Testing API key...")
    print(f"Key: {api_key[:20]}...{api_key[-10:]}")
    print()

    try:
        client = Anthropic(api_key=api_key)

        # Try a simple request
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=50,
            messages=[
                {"role": "user", "content": "Say 'Hello, API test successful!'"}
            ]
        )

        # Print response
        print("✅ API Key Valid!")
        print(f"Response: {response.content[0].text}")
        print(f"Model: {response.model}")
        print(f"Tokens Used: {response.usage.input_tokens + response.usage.output_tokens}")
        return True

    except AuthenticationError as e:
        print(f"❌ Authentication Failed: {e}")
        print()
        print("Your API key is invalid or expired.")
        print("Please get a new key from: https://console.anthropic.com/")
        return False

    except APIError as e:
        if "not_found_error" in str(e):
            print(f"❌ Model Not Found: {e}")
            print()
            print("The model 'claude-3-sonnet-20240229' is not available.")
            print("Trying alternative models...")

            # Try other models
            for model in ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"]:
                print(f"\nTrying {model}...")
                try:
                    client = Anthropic(api_key=api_key)
                    response = client.messages.create(
                        model=model,
                        max_tokens=50,
                        messages=[{"role": "user", "content": "Hello"}]
                    )
                    print(f"✅ Model {model} works!")
                    print(f"Update CLAUDE_MODEL={model} in your .env file")
                    return True
                except:
                    print(f"✗ {model} not available")
                    continue

            print()
            print("No models available. Check your API access.")
            return False
        else:
            print(f"❌ API Error: {e}")
            return False

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # API key provided as argument
        api_key = sys.argv[1]
    else:
        # Read from .env file
        try:
            from src.utils.config import get_config
            config = get_config()
            api_key = config.ANTHROPIC_API_KEY
            print("Using API key from .env file")
            print()
        except Exception as e:
            print(f"Error loading .env: {e}")
            print()
            print("Usage: python scripts/test_api_key.py [API_KEY]")
            print("Or update your .env file and run without arguments")
            sys.exit(1)

    if not api_key or api_key == "your-api-key-here":
        print("❌ No API key configured!")
        print()
        print("Please update ANTHROPIC_API_KEY in .env file")
        print("Get a key from: https://console.anthropic.com/")
        sys.exit(1)

    # Test the key
    if test_api_key(api_key):
        print()
        print("=" * 60)
        print("✅ SUCCESS - Your API key is working!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("1. Make sure your .env file has the correct API key")
        print("2. Launch the UI: ./run_ui.sh")
        print("3. Or test the agent: python src/intelligence/agent.py")
        sys.exit(0)
    else:
        print()
        print("=" * 60)
        print("❌ FAILED - API key not working")
        print("=" * 60)
        print()
        print("Please:")
        print("1. Get a new API key from https://console.anthropic.com/")
        print("2. Update ANTHROPIC_API_KEY in .env file")
        print("3. Run this test again")
        sys.exit(1)


if __name__ == "__main__":
    main()
