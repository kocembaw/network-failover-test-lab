---
name: Defect
about: A test case failed or the lab behaved unexpectedly
title: "[TC-xx] "
labels: defect
---

## Summary
<!-- One sentence: what is wrong, and which requirement is not met. -->

| | |
|---|---|
| Test case | TC-xx |
| Requirement | REQ-xx |
| Test run | RUN-YYYY-MM-DD |
| Severity | Critical / Major / Minor |
| Priority | High / Medium / Low |
| Lab config | commit `<hash>` |

## Steps to reproduce
1.
2.
3.

## Expected result

## Actual result
<!-- Include the probe report or command output. -->

## Evidence
<!-- Links to files in results/evidence/<run>/: probe log, router state, pcap. -->

## Root cause analysis
<!-- Timeline (UTC): fault injected, OSPF reaction, traffic recovered. Why did it behave this way? -->

## Fix
<!-- Config change and commit that fixes it. -->

## Retest
<!-- Run ID and result of the failed test case and of the regression set (TC-01, TC-02, TC-04, TC-07). -->
