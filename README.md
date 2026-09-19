# doc-follow-up

Manage open client documentation requests across a bookkeeping team: register what you need, track deadlines, draft contextual follow-up emails, and close the loop when documents arrive.

Built as an [Interpretable Context Methodology (ICM)](https://github.com/RinDig/Interpretable-Context-Methodology) workspace — folder structure as agent architecture. One agent, reading the right files at the right moment, works through a five-stage pipeline with a shared CSV tracker as the connective state.

## Folder map

```
doc-follow-up/
├── CLAUDE.md              entry point -- always loaded
├── CONTEXT.md             task routing
├── setup/
│   └── questionnaire.md   onboarding -- run with "setup"
├── shared/
│   ├── tracker.csv        master request tracker -- the backbone
│   ├── follow-up-rules.md deadline-driven follow-up schedule
│   └── email-defaults.md  firm name, signature, reply-to
├── stages/
│   ├── 01-register/       add new documentation requests
│   ├── 02-assess/         determine what needs follow-up today
│   ├── 03-draft/          write contextual follow-up emails
│   ├── 04-receive/        log incoming docs, run pre-check
│   └── 05-review/         accept, reject, or override
└── test-data/             fictional (LOTR-themed) mock documents for testing
```

## Triggers

| Keyword | Action |
|---------|--------|
| `setup` | Run onboarding questionnaire -- configures firm name, team, defaults |
| `status` | Show pipeline status and open item counts |
| `register` | Jump to Stage 01 to add a new request |
| `assess` | Jump to Stage 02 to check what needs follow-up today |
| `draft` | Jump to Stage 03 to write follow-up emails |
| `received` | Jump to Stage 04 to log an incoming document |
| `review` | Jump to Stage 05 to accept or reject a received document |

## Stage flow

The tracker CSV is the shared state that connects everything. This is not a linear pipeline -- stages run in any order based on what the team needs right now.

1. **Register** writes new rows to the tracker
2. **Assess** reads the tracker to find items due for follow-up
3. **Draft** reads Stage 2 output + tracker to write emails
4. **Receive** updates tracker status from Open to Received
5. **Review** updates tracker status to Accepted or Returned (back to Open)

## Getting started

1. Clone this repo
2. Open Claude Code (or Claude Desktop) in this folder
3. Type `setup` and answer the onboarding questions
4. Start working the pipeline -- type `status`, `register`, `assess`, `draft`, `received`, or `review`

## Test data

`test-data/` and `shared/tracker.csv` ship pre-populated with fictional clients (Baggins & Associates, Rohan Cavalry Services, and similar) so you can run the full pipeline end-to-end before pointing it at real client data.

## License

MIT

