# Prompts — LLM Prompt Templates

## Purpose
All Mistral system prompts and prompt templates live here, version-controlled and separated from code. This is critical because prompt quality directly determines product quality — the interview, profile extraction, persona generation, and conversation all depend on well-crafted prompts.

## Why Separate From Code
- Prompts are iterated on independently from code logic
- They can be reviewed, A/B tested, and versioned without touching Python
- Keeps engine classes clean — they load a prompt, inject variables, and send to Mistral
- Makes it easy to swap prompts during the hackathon without restarting the server

## Prompt Files

### `interview.md`
System prompt for the **InterviewAgent**. Defines:
- The interviewer's neutral, impersonal tone
- The categories of information to extract (values, fears, tensions, decision style, dilemma)
- Rules for when to probe deeper vs. move on
- Criteria for when the interview has gathered enough signal to end
- Instructions to never advise, judge, or reveal the purpose of specific questions

### `profile_extraction.md`
System prompt for the **ProfileBuilder**. Defines:
- How to synthesize a raw transcript into a structured UserProfile
- How to identify hidden tensions (contradictions between stated values)
- How to generate the current self persona card from the profile
- Output format (JSON matching the UserProfile + SelfCard schemas)

### `future_self_generation.md`
System prompt for the **FutureSelfGenerator**. Defines:
- How to take a profile + dilemma and branch into contrasting futures
- Rules for creating meaningful variation (not just optimistic vs. pessimistic)
- Each self must optimize for something real and sacrifice something real
- Output format (JSON array of SelfCard objects)
- Guidance on visual style assignment (colors, mood, glow)

### `conversation.md`
System prompt template for the **ConversationEngine**. This is a template, not static:
- Injects the selected SelfCard's persona details (tone, worldview, beliefs)
- Injects the user profile for context
- Injects current memory facts
- Rules: stay in character, never break persona, never admit to being AI
- Guidance on conversation depth (challenge the user, don't just agree)
- Instructions for what facts to extract and remember from each exchange

### `summarize.md`
System prompt for the **debrief summary**. Defines:
- How to summarize what this future self optimizes for
- What it sacrifices and what it gains
- Key moments from the conversation
- Output format for the debrief screen

## Variable Injection Pattern
Prompts use `{{variable_name}}` placeholders that get replaced at runtime:
- `{{user_profile}}` — serialized UserProfile
- `{{self_card}}` — serialized SelfCard
- `{{conversation_history}}` — formatted message list
- `{{memory_facts}}` — list of extracted key facts
- `{{dilemma}}` — the user's current dilemma

## TODO
- [ ] Write interview system prompt (neutral interviewer, 5-8 questions)
- [ ] Write profile extraction prompt with JSON output format
- [ ] Write future self generation prompt with variation rules
- [ ] Write conversation prompt template with persona injection
- [ ] Write summarize prompt for debrief screen
- [ ] Test each prompt standalone with Mistral before integrating
- [ ] Iterate on interview prompt to get natural, probing questions
