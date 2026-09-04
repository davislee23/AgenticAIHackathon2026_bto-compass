import os

def get_active_provider_info():
    """Returns metadata about the currently configured LLM provider."""
    provider = os.getenv("LLM_PROVIDER", "bedrock").lower()
    
    if provider == "groq":
        return {
            "provider": "Groq",
            "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            "icon": "⚡"
        }
    else:
        return {
            "provider": "AWS Bedrock",
            "model": os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-haiku-20241022-v1:0"),
            "icon": "☁️"
        }

def get_llm():
    info = get_active_provider_info()
    provider = os.getenv("LLM_PROVIDER", "bedrock").lower()

    # Log active provider banner in terminal console
    print(f"\n==================================================")
    print(f" {info['icon']} ACTIVE LLM PROVIDER: {info['provider']}")
    print(f"   MODEL: {info['model']}")
    print(f"==================================================\n")

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=info["model"],
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0.0
        )

    elif provider == "bedrock":
        # Crucial: Import ChatBedrockConverse (Converse API), NOT ChatBedrock or Bedrock
        from langchain_aws import ChatBedrockConverse
        
        return ChatBedrockConverse(
            model=info["model"],
            region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
            temperature=0.0
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
