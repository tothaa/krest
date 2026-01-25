# KREST - call REST endpoints with faith
KREST is a lightweight desktop application for testing and invoking HTTP-based web services.


It is a free and open-source (GPLv2) tool that stores your data locally and encrypted at-rest.

Designed for developers with good intentions who value simplicity, privacy and integrity.

KREST utilizes the `httpx` python package within a user-friendly interface. It provides a Workspace to organize your API requests without the bloat of enterprise suites.


## Dependencies
You need to have python and pip installed on your system (https://www.python.org/).
The pip will also automatically install the other dependencies: httpx, cryptography, textual.

## Installation
Install from https://pypi.org/ central repository:
> pip install krest

## Running the Application
> krest

## Features
* TUI: text-based user interfaces included to run the application with minimal dependencies.
  > krest-tui
* Encrypted Storage: store your data locally in a password-protected file (AES-256-GCM).
* Endpoint Management: specify and organize your API-request details and Credentials for re-use.
* Call History: analyze your previous requests and API responses.

## Supporting my Work
* Submit bug reports - https://github.com/tothaa/krest/issues
* Contribute to the code - https://github.com/tothaa/krest
* Donate:
  Say thank you with a tip to the developer. 
  Donations also motivate me to spend more time on Enhancements and Bugfixes.
  + GitHub Sponsors - https://github.com/sponsors/tothaa
  alternatively:
  + Librepay - https://liberapay.com/tothaa
  + ko-fi: https://ko-fi.com/tothaa

## Roadmap
### Done
minimal backend, minimal TUI

### Next
* [ ] code quality: improved logging, log-level settings into project file
* [ ] code quality: update developer test cases, review type annotations
* [ ] GUI: adding KDE/Kirigami Qt-based ui implementation
* [ ] TUI: filter, sort of Endpoints, Credentials, History
* [ ] configuration: option for backups control
* [ ] bugfixing: improve Call History Details screens and performance; decide what to include in the history records.
* [ ] bugfixing: be more consistent on how to use httpx.Client.request() function data and json attributes
* [ ] code quality: refactoring input validations.
* [ ] Feature: parallel httpx calls and stress-test
* [ ] Feature: support for variables
* [ ] Feature: support for sending and receiving files
* [ ] Feature: support for workflows, simple automated testing scripts
* [ ] Feature: support for multipart payload
* [ ] Feature: support for more authentication types
* [ ] Feature: CLI interface for automation with shell scripts
* [ ] Feature: support for httpx advanced features - http2, brotli, zstd
* [ ] Feature: optional MCP interface
* [ ] Feature: ignore proxy settings (maybe: `with httpx.Client(trust_env=False) as client:`)
* [ ] TUI: Feature: delete a credential
* [ ] Feature: cleanup history
* [ ] TUI: Feature: change project file password
* [ ] bugfixing: add locking file feature - if multiple instances are running, file should be opened only once.
* [ ] TUI: Feature: add actions into the Command Palette
* [ ] TUI: improve texsts/labels consistency.

### Not Doing
* ~~cloud sync~~

## Guides and Demos
Check the youtube channel: 
  https://www.youtube.com/channel/UCemj-6NUaVcvaa-GbVCc5Ug
* Disclaimer and About the Krest Project (Part 1)
* TUI - Managing the Project Files (Part 2)
* TUI - Managing Credentials (Part 3)
* TUI - Managing Endpoints (Part 4)
* TUI - Calling Endpoints (Part 5)
