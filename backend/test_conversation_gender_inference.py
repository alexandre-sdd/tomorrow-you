from __future__ import annotations

import unittest

from backend.routers.conversation import _infer_voice_gender


class ConversationGenderInferenceTests(unittest.TestCase):
    def test_detects_explicit_self_identification_male(self) -> None:
        gender = _infer_voice_gender(
            self_card={},
            user_profile={"self_narrative": "I'm a man trying to make a hard career decision."},
        )
        self.assertEqual(gender, "male")

    def test_detects_explicit_self_identification_female(self) -> None:
        gender = _infer_voice_gender(
            self_card={},
            user_profile={"self_narrative": "I am a woman balancing family and growth."},
        )
        self.assertEqual(gender, "female")

    def test_ignores_relationship_words_that_do_not_identify_self(self) -> None:
        gender = _infer_voice_gender(
            self_card={},
            user_profile={"self_narrative": "My wife and her parents are affected by this choice."},
        )
        self.assertIsNone(gender)

    def test_prefers_explicit_profile_gender(self) -> None:
        gender = _infer_voice_gender(
            self_card={},
            user_profile={
                "gender": "male",
                "self_narrative": "I am a woman in tech.",  # conflicting text
            },
        )
        self.assertEqual(gender, "male")

    def test_maps_free_text_personal_gender_aliases(self) -> None:
        male = _infer_voice_gender(
            self_card={},
            user_profile={"personal": {"gender": "guy"}},
        )
        female = _infer_voice_gender(
            self_card={},
            user_profile={"personal": {"gender": "she/her"}},
        )
        self.assertEqual(male, "male")
        self.assertEqual(female, "female")


if __name__ == "__main__":
    unittest.main()
