from src.modules.search.spellcheck import parse_spellcheck_suggestions


def test_parse_spellcheck_suggestions_returns_top_three_unique_candidates():
    payload = {
        "matches": [
            {
                "replacements": [
                    {"value": "iphone"},
                    {"value": "iPhone"},
                    {"value": "phone"},
                ]
            },
            {
                "replacements": [
                    {"value": "headphone"},
                    {"value": "smartphone"},
                ]
            },
        ]
    }

    suggestions = parse_spellcheck_suggestions(payload, "ihone")

    assert suggestions == ["iphone", "phone", "headphone"]


def test_parse_spellcheck_suggestions_skips_original_word():
    payload = {
        "matches": [
            {
                "replacements": [
                    {"value": "телефон"},
                    {"value": "телефона"},
                ]
            }
        ]
    }

    suggestions = parse_spellcheck_suggestions(payload, "телефон")

    assert suggestions == ["телефона"]
