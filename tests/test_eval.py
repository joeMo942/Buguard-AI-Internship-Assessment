import pytest
import asyncio
from app.ai.llm import get_llm
from app.ai.guardrails import validate_asset_references

@pytest.mark.asyncio
async def test_llm_hallucination_guardrails():
    """
    Evaluates the guardrail logic to ensure it accurately detects hallucinated 
    asset IDs and values versus real ones.
    """
    known_ids = {"a1", "a2"}
    known_values = {"example.com", "192.168.1.1"}
    
    # Test 1: Perfectly grounded text
    grounded_text = "The asset `example.com` (ID a1) is secure."
    result1 = validate_asset_references(grounded_text, known_ids, known_values)
    assert result1["is_grounded"] is True
    assert len(result1["hallucinated_ids"]) == 0
    assert len(result1["hallucinated_values"]) == 0

    # Test 2: Hallucinated ID
    hallucinated_id_text = "The asset `example.com` (ID a99) is at risk."
    result2 = validate_asset_references(hallucinated_id_text, known_ids, known_values)
    assert result2["is_grounded"] is False
    assert "a99" in result2["hallucinated_ids"]
    
    # Test 3: Hallucinated Value
    hallucinated_val_text = "The asset `malicious.com` (ID a2) requires attention."
    result3 = validate_asset_references(hallucinated_val_text, known_ids, known_values)
    assert result3["is_grounded"] is False
    assert "malicious.com" in result3["hallucinated_values"]

@pytest.mark.asyncio
async def test_llm_chain_output_formatting():
    """
    Evaluates that the LLM is capable of generating valid outputs 
    and handles system prompts correctly.
    """
    llm = get_llm(temperature=0.0)
    response = await llm.ainvoke([("user", "Return exactly the word 'SUCCESS' and nothing else.")])
    
    text = response.content
    if isinstance(text, list):
        text = text[0].get("text", "")
        
    assert "SUCCESS" in text.strip()
