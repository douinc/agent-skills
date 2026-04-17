---
name: onboarding-design
description: Use when designing, implementing, or auditing product onboarding flows — signup screens, personalization quizzes, paywalls, permission prompts, or any screen between first launch and the user's aha moment.
---

# Onboarding Design

Onboarding is the product's job interview. Focus every decision on the shortest path to the **aha moment**: the first instant the user *feels* the core value personally.

## Core Principles

### 1. Outcomes Over Features

Never list features. Show what the user's life looks like after using the product.

| Instead of | Write |
|------------|-------|
| "Learn vocabulary and grammar" | "Have real conversations in Paris" |
| "Track your calories" | "Fit into those jeans by August" |
| "Organize your tasks" | "Leave work on time, every day" |

Every headline must describe a user outcome, not a product capability.

### 2. Drive to the Aha Moment

Map every screen between signup and the aha moment. Delete anything that doesn't move the user closer to it.

- **Airbnb:** first booking confirmation
- **Spotify:** first song played from a personalized playlist
- **Duolingo:** first lesson completed with a streak started

### 3. Personalization First

Collect the user's goal before showing anything generic. Use their answer to:
- Reorder feature highlights
- Drive paywall copy and plan recommendation
- Set the initial dashboard state

Never show a generic welcome screen to a user who has already told you their goal.

### 4. Delightful Friction

Short onboarding is not always better. Duolingo's 60-screen flow outperforms shorter ones because each screen delivers micro-progress and builds commitment. Delight through:

- **Progress indicators** — show steps completed, not steps remaining
- **Loading animations** — "Analyzing your answers..." frames waiting as personalization work
- **Micro-copy that celebrates** — "Nice! 3 of 5 done"

Replace every neutral transition screen with one that celebrates progress or sets expectations.

### 5. Human Touch

At least one screen before the paywall must feel like it came from a person:
- Founder photo or short video on the welcome screen
- "Written by [Name], CEO" attribution on value propositions
- Handwritten-style typography for personal messages

### 6. Pre-Permission Screens

Never trigger a native permission dialog without first explaining the benefit.

```
Custom screen: "We'll send daily streaks so you never lose progress."
    [I want to stay on track]    [Not now]
         ↓
    Native OS dialog
```

Use first-person framing for the confirm action: "I want to stay on track."

### 7. Multi-Intent Support

Users have more than one goal. Allow multiple selections (Headspace model), rank them to infer primary intent, and use the full combination for downstream personalization — not just the first pick.

## Monetization

### Personalized Paywall

The highest-converting paywall copy references what the user just told you.

```
Quiz: "What is your main goal?" → "Lose weight"

Paywall: "Your personalized weight-loss plan is ready.
          Most users with your goal reach their target in 8 weeks."
```

Grammarly's personalized approach produced a 20% lift in upgrade rates over generic copy. The paywall must contain at least one sentence referencing the user's specific quiz answer.

### Unlock Value Animation

After the quiz, make personalization feel tangible before revealing the paywall:

```
"Building your plan..."
[Progress bar fills]
[✓ Goal identified  ✓ Schedule optimized  ✓ Plan ready]
"Your 8-week plan is ready."
```

## Audit Checklist

- [ ] Every headline describes a user outcome (not a feature)
- [ ] The aha moment is identified and all screens before it are justified
- [ ] Quiz answers drive subsequent screen content
- [ ] Progress indicators show completion, not remaining steps
- [ ] Every native permission has a pre-permission screen first
- [ ] Goal/intent questions allow multiple selections
- [ ] The paywall references the user's specific quiz answer
- [ ] At least one screen has a human touch element

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Feature carousel at launch | Outcome-focused value screens |
| Single-choice goal selector | Multi-select with ranking |
| Native permission dialog with no context | Pre-permission screen first |
| Generic paywall copy | Reference quiz answers in headline |
| Progress bar showing steps remaining | Show steps completed |
| Long form before any value | Deliver one value moment before data collection |

## Related Skills

- `user-onboarding` — Strategic principles and aha moment frameworks
- `behavioral-product-design` — Psychological patterns in product design
- `retention-engagement` — Post-onboarding engagement loops
