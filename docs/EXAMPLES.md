# Paradigme: research walkthrough

[Back to the README](../README.md)

## Example: local AI and software teams

1. Start the application and complete the setup wizard with your chosen LLM endpoint.
2. Enter the subject: **How might local AI adoption affect small software teams?**
3. Add context: **Explore a hypothetical team of five developers over the next two years. Treat this as a scenario, not a forecast.**
4. Select the public sources relevant to the question. Start with the Classic analysis model.
5. Submit the analysis and follow its progress. Source and model requests require connectivity to their configured endpoints.
6. Review the evidence, sector analysis, decision tree and conditional scenarios.
7. Export the PDF or text report after checking citations and assumptions.

This example contains synthetic context. It does not describe a real team or
promise a particular outcome. Generated scores and probabilities are not calibrated forecasts.

## Compare two contexts

Repeat the subject with one changed assumption, such as limited hardware versus
access to a dedicated inference server. Keep the other inputs as consistent as
possible. Compare the reports and trace differences back to the assumptions and
sources; model variability can also affect the result.

## Choose an analysis model

| Mode | Intended use | Interpretation |
| --- | --- | --- |
| Classic | General research and scenario exploration | Review evidence and conditional reasoning |
| Turchin | Optional exploration of cycles, stress and timelines | Treat dates, curves and scores as exploratory illustrations |

## Review before sharing

- Open cited sources and confirm that they support the relevant claims.
- Separate observed facts, assumptions and generated interpretations.
- Remove private context and credentials from anything you share.
- Keep uncertainty visible in exported reports.

Public-source research sends queries to external services. The configured LLM
receives collected context; a cloud endpoint therefore receives that content.
Email is optional and disabled by default. See [privacy](PRIVACY.md) and the
[technical guide](../CAHIER_TECHNIQUE.md) for configuration and API details.
