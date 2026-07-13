def extract_text_from_response(response) -> str:
    """
    Extracts plain text from LLM response content.

    Gemma 4 returns content as a list of blocks:
      [
        {'type': 'thinking', 'thinking': '...'},  ← internal reasoning
        {'type': 'text', 'text': '...'}            ← actual response
      ]

    Other models return content as a plain string.
    This function handles both cases uniformly.

    Why centralise here?
    Every agent calls LLM and needs this extraction.
    One function here means one place to fix if response
    format changes with model updates.
    """
    content = response.content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts)

    return content