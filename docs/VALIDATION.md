# Validation

Run `python -m unittest discover -s tests -v` using the project environment.

Privacy tests use synthetic identities and temporary repositories. Application
tests use isolated settings/storage, mocked providers, and synthetic results.
They must not contact a real model, send email, or change user settings.
Publication requires source and complete Git-object audits.

Automated checks do not establish factual accuracy. Live provider availability,
research results, and SMTP delivery need separate user-controlled checks.

## Release checks

The public snapshot passed 23 regression tests, JavaScript syntax checks, a browser
check of setup/settings/history and reopening a saved result, and a visual review
of all six pages of a synthetic English PDF. No real inference or email was sent.
Source and Git-object audits were run with a private reference list outside the
repository. Original history and local backup files were preserved outside it.
