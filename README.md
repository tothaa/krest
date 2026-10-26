# KREST - call REST endpoints with faith
KREST is a lightweight desktop application for testing and invoking HTTP-based web services. <br /><br />


It is a free and open-source (GPLv2) tool that stores your data locally and encrypted at-rest.

Designed for developers with good intentions who value simplicity, privacy and integrity.

KREST utilizes the `httpx` python package within a user-friendly interface. It provides a Workspace to organize your API requests without the bloat of enterprise suites.


## Installation
### Dependencies
You need to have python and pip installed on your system (https://www.python.org/).
The pip will also automatically install the other dependencies: httpx, cryptography, textual.

### Install from PyPi
Install from https://pypi.org/ central repository:
> pip install krest-utils

### Launcher Icon and File Associations
Run script for setting up the icon and file associations:
> krest-post-install

On Linux:
1. right click on a `.krest` file,
2. choose **Open With**,
3. choose `krest`,
4. set the default with: `xdg-mime default org.kde.krest.file.desktop application/x-krest` .

## Running the Application
> krest

Options:
* --file or -f for opening an existing file inmediatelly (`krest --file <file_path>`).
* --debug or -d for saving run logs into `krest.log` file. **Note**: you might save sensitive info to the log file, delete the log file after use!

## Features
* TUI: text-based user interfaces included to run the application with minimal dependencies.
  > krest-tui
* Encrypted Storage: store your data locally in a password-protected file (AES-256-GCM).
* Endpoint Management: specify and organize your API-request details and Credentials for re-use.
* Call History: analyze your previous requests and API responses.

## Guides and Demos
Check the youtube channel: 
  https://www.youtube.com/channel/UCemj-6NUaVcvaa-GbVCc5Ug
* Disclaimer and About the Krest Project (Part 1)
* TUI - Managing the Project Files (Part 2)
* TUI - Managing Credentials (Part 3)
* TUI - Managing Endpoints (Part 4)
* TUI - Calling Endpoints (Part 5)

## Supporting my Work
* Submit bug reports       - https://github.com/tothaa/krest/issues
* Contribute to the code   - https://github.com/tothaa/krest
* Donate:

  Say thank you with a tip to the developer.

  Donations also motivate me to spend more time on Enhancements and Bugfixes.
  + 4Fund - https://4fund.com/hu/vhynh2

  ***Alternatives***
  + GitHub Sponsors - https://github.com/sponsors/tothaa
  + Librepay - https://liberapay.com/tothaa
  + ko-fi - https://ko-fi.com/tothaa
  + PayPal - https://paypal.me/tothaaprojects

## Roadmap

### Next
* [ ] code quality: update developer test cases
* [ ] code quality: review type annotations
* [ ] code quality: review copy and deepcopy, when returned a copy, when returned a reference - and if dirty bit updated correctly.
* [ ] code quality: to review: consider using attrs with classes instead of dict (`from attrs import define, field, validators`, attrs.asdict() and attrs.assoc() for easy dict/json transformation)
* [ ] code quality: refactoring input validations.
* [ ] Feature: rewrite to async of run_endpoint()
* [ ] GUI: adding KDE/Kirigami Qt-based ui implementation
  target v1.0.6
* [ ] bugfixing: TUI: improve Call History Details performance
* [ ] bugfixing: be more consistent on how to use httpx.Client.request() function data and json attributes
* [ ] Feature: parallel httpx calls and stress-test
* [ ] Feature: support for variables
  target v1.0.5
* [ ] Feature: support for workflows, simple automated testing scripts
  target v1.0.5
* [ ] Feature: support for more authentication types
* [ ] Feature: CLI interface for automation with shell scripts
* [ ] Feature: support for httpx advanced features - http2, brotli, zstd
* [ ] Feature: optional MCP interface

### Done
* [x] minimal backend, minimal TUI
* [x] code quality: improved logging, log-level settings ~~~into project file~~~ command line parameter with 1.0.3.
* [x] TUI: sort Endpoints, Credentials, History - v1.0.4
* [x] TUI: improve texsts/labels consistency. - updated the locales already with 1.0.3.
* [x] TUI: filter for Endpoints, Credentials, History - v1.0.4
* [x] TUI: select first item in DataTables on initialization - v1.0.4
* [x] TUI: Feature: delete a credential - v1.0.4
* [x] open file from command line with - v1.0.4.
* [x] configuration: options for backups control in properties/settings page - v1.0.4
* [x] Feature: ignore proxy settings (maybe: `with httpx.Client(trust_env=False) as client:`) - v1.0.4
* [x] Feature: cleanup history; add retention to Settings - v1.0.4
* [x] TUI: Feature: change project file password - v1.0.4
* [x] TUI: Feature: add actions into the Command Palette - v1.0.4
* [x] bugfixing: add locking file feature - if multiple instances are running, file should be opened only once. - v1.0.4
* [x] Feature: support for sending files - v1.0.4
* [x] Feature: support for multipart payload - v1.0.4
* [x] Feature: support for receiving files - v1.0.4
* [x] bugfixing: improve Call History Details screens: decide what to include in the history records. - v1.0.4

### Not Doing
* ~~cloud sync~~

