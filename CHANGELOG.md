# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Plugin skeleton: manifest, marketplace file, folder layout, MIT licence.
- Trip file schema (`schemas/trip.schema.json`) and user profile schema (`schemas/profile.schema.json`).
- `scripts/validate.py`: checks a trip file or a user profile against its schema and the coherence rules; standard library only, Python 3.9 or later.
- Tests for the checks.
