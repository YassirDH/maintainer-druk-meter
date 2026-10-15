# Test report: how often is the model right?

*50 comments from the live stream, labelled blind (the model's verdict was hidden while labelling). Sample: random, at most 10 per project, seed 42, bot commands excluded.*

**My labels:** negative 14, neutral 27, positive 9

## Overview

| Method | Agrees with me | Macro-F1 | Negatives caught (recall) | Flagged negative and correct (precision) |
|---|---|---|---|---|
| Model 1 (twitter-roberta, live) | 72% | 0.66 | 71% | 77% |
| Model 2 (xlm-roberta, multilingual) | 64% | 0.63 | 79% | 55% |
| Word list (no AI) | 38% | 0.36 | 29% | 36% |
| *Always say 'neutral'* | 54% | – | – | – |

*Agrees with me* = share of comments where the method gives the same label as I did. *Macro-F1* = average over the three classes, so a method cannot score well by always saying 'neutral'. *Negatives caught* matters most for the user: how many of the truly negative comments does the meter pick up?

## Confusion matrices

Rows = my label, columns = what the method said.

**Model 1 (twitter-roberta, live)**

| me \ method | negative | neutral | positive |
|---|---|---|---|
| **negative** | 10 | 4 | 0 |
| **neutral** | 3 | 23 | 1 |
| **positive** | 0 | 6 | 3 |

**Model 2 (xlm-roberta, multilingual)**

| me \ method | negative | neutral | positive |
|---|---|---|---|
| **negative** | 11 | 2 | 1 |
| **neutral** | 9 | 16 | 2 |
| **positive** | 0 | 4 | 5 |

**Word list (no AI)**

| me \ method | negative | neutral | positive |
|---|---|---|---|
| **negative** | 4 | 9 | 1 |
| **neutral** | 7 | 11 | 9 |
| **positive** | 0 | 5 | 4 |

## Every error of model 1

Pick the three (or more) to explain in the README from here. The note is what I wrote while labelling.

| # | Project | Comment | Me | Model 1 (confidence) | Model 2 | Word list | Note |
|---|---|---|---|---|---|---|---|
| 1 | nodejs/node | Thanks for spotting this! Reported upstream in isaacs/minimatch#329, it's a regression since 10.2.3. | positive | neutral (64%) | neutral | neutral |  |
| 2 | rust-lang/rust | Yeah makes sense, though it irks the perfectionist in me. ;) I'll make this docs-only (and maybe a no-functional-change refactor if I think there's anything left of my original refactor idea). @user author | positive | neutral (44%) | positive | neutral |  |
| 3 | kubernetes/kubernetes | Hi @user, I've addressed your feedback and pushed the updates in commit . - Fixed event-handling latency measurement to capture the start time before processing. - Removed the unrealistic same-resource-version, different-UID test cases. - Added queueing-hint regression tests veri… | positive | neutral (68%) | neutral | neutral |  |
| 4 | home-assistant/core | Same issue here with my Tuya blind: open/close and position are reversed in HA, but it works fine in the Smart Life app. Since this seems to keep happening with different motors, would it be possible to add an "invert position" option in the Tuya integration (per device/entity)?… | negative | neutral (74%) | neutral | neutral |  |
| 5 | rust-lang/rust | Behavior 2 seems likely to cause issues for code like this, which I have written: | neutral | negative (74%) | negative | neutral |  |
| 6 | python/cpython | @user - Kicked off [another run](http Fingers crossed this one works. | positive | neutral (55%) | positive | positive |  |
| 7 | golang/go | **2026-10-14 / @user, @user, @user, @user, @user, @user** **Discussions (not yet proposals)** - **gabyhelp feedback** [#67901](http - **x/oscar feedback** [#68490](http - **memory regions** [#70257](http - **a more robust proposal process** [#80580](http - **gonew: templates for… | positive | neutral (94%) | neutral | positive |  |
| 8 | openssl/openssl | Sure, I can put in draft. I didn't thought that it will be resolved so quickly. | positive | neutral (66%) | positive | neutral |  |
| 9 | openssl/openssl | What puzzles me is fast that you (@user) have reported which means that you must have passed the reported error, and now we're seeing it again. Is there any chance you accidentally dropped patches? | neutral | negative (78%) | negative | negative |  |
| 10 | kubernetes/kubernetes | This pending pods deletion logic seems for me quite generic. Is there any reason why we couldn't extract it to a dedicated PodGroup controller which could delete pending pods for all preempted PodGroups? | neutral | negative (60%) | negative | neutral |  |
| 11 | openssl/openssl | That's very weird... But, would you mind trying #33218 for size? I've ended up preferring that one. | negative | neutral (55%) | negative | neutral |  |
| 12 | home-assistant/core | The public API does report smoke and CO alarms ( with the alarm type) and the detector's maintenance events. We're not adding them for now. We can't verify the delivery end to end: CO not at all, smoke only with test spray, and most maintenance events can't be triggered on demand… | negative | neutral (51%) | negative | neutral |  |
| 13 | nextcloud/server | May I propose we prioritize the search option? Finding the items without any apparent ordering is getting a real pita 😅 I know we attempt to order by relevance but that is.. though. I’d think a simple filter on top would do wonders. If that filter searches through ALL config sett… | negative | neutral (56%) | positive | neutral |  |
| 14 | nextcloud/server | This looks like it'll have to happen in http The underlying emoji Picker does have some support it seems: http | neutral | positive (55%) | neutral | neutral |  |

## Jargon probe (made-up sentences, not from the stream)

Technical language that sounds negative in everyday English. Does the model read the tone or the words?

| Sentence | Intended | Model 1 | Model 2 | Word list |
|---|---|---|---|---|
| Kill the process and restart the daemon, then it works. | neutral | neutral ✓ | neutral ✓ | positive ✗ |
| This fixes a fatal error in the parser. | positive | neutral ✗ | negative ✗ | negative ✗ |
| The test suite crashes on ARM, here is the backtrace. | neutral | negative ✗ | negative ✗ | negative ✗ |
| Deprecated in 3.12 and removed in 3.14. | neutral | neutral ✓ | neutral ✓ | neutral ✓ |
| Thanks, this was a terrible bug and your patch solves it! | positive | negative ✗ | negative ✗ | negative ✗ |
| Abort the build if the checksum doesn't match. | neutral | negative ✗ | negative ✗ | neutral ✓ |
| Third time I'm asking. Is anyone actually maintaining this? | negative | neutral ✗ | neutral ✗ | neutral ✗ |
| Great, another release that breaks my setup. Well done. | negative | positive ✗ | positive ✗ | positive ✗ |

## xz look-back: would the meter have seen the pressure?

The real 2022 messages with which (probably fake) accounts pressured the sole xz maintainer, two years before the backdoor CVE-2024-3094. Source: [Russ Cox, xz timeline](https://research.swtch.com/xz-timeline). Intended label: negative (pressure on the maintainer).

| Date | Account | Message | Model 1 | Model 2 | Word list |
|---|---|---|---|---|---|
| 2022-04-22 | Jigar Kumar | Patches spend years on this mailing list. There is no reason to think anything is coming soon. | negative (72%) | neutral | neutral |
| 2022-05-27 | Jigar Kumar | Over 1 month and no closer to being merged. Not a surprise. | neutral (54%) | neutral | neutral |
| 2022-06-07 | Jigar Kumar | Progress will not happen until there is new maintainer. | negative (50%) | neutral | neutral |
| 2022-06-14 | Jigar Kumar | With your current rate, I very doubt to see 5.4.0 release this year. | negative (84%) | neutral | neutral |
| 2022-06-21 | Dennis Ens | I am sorry about your mental health issues, but its important to be aware of your own limits. | negative (56%) | negative | neutral |
| 2022-06-22 | Jigar Kumar | Why can't you commit this yourself? | negative (81%) | negative | neutral |

Model 1 flags **5 of the 6** messages as negative. Note: these messages were posted on a mailing list, not on GitHub, so the meter would not have seen them at all.
