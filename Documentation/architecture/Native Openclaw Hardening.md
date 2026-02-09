Given my current state (already installed + Telegram input),
  here is a hardening-first procedure before vault access.

  1. #### Create a control plane directory (inference)

  - Create a private repo, e.g. ~/ops/openclaw-control/ with:
      - config/openclaw.json (tracked)
      - launchd/bot.molt.gateway.plist (tracked)
      - env/openclaw.env (not tracked, chmod 600)
      - playbooks/upgrade.md (tracked)
  - This gives you auditable config + repeatable ops.

  2. #### Lock file permissions now

  - Run:
      - chmod 700 ~/.openclaw
      - chmod 600 ~/.openclaw/openclaw.json
      - openclaw doctor
      - openclaw security audit --deep
  - Fix any findings before continuing.

  3. #### Freeze runtime versions (inference)

  - Pin Node runtime used by OpenClaw:
      - brew install node@22
      - brew pin node@22
      - node -v
  - Pin OpenClaw package version (not latest) for stability:
      - npm i -g openclaw@<known_good_version>
  - Note: OpenClaw docs require Node 22+, but Telegram troubleshooting currently
    mentions a Node 22 abort edge case; if you hit it, temporarily pin Node 20
    until upgraded.

  4. #### Harden gateway network/auth in config

  - In ~/.openclaw/openclaw.json set:
      - gateway.bind: "loopback"
      - gateway.tailscale.mode: "serve"
      - gateway.auth.mode: "password"
      - gateway.auth.password: "${OPENCLAW_GATEWAY_PASSWORD}"
      - gateway.auth.allowTailscale: false (require explicit auth even on
        tailnet)
      - discovery.mdns.mode: "off" (or at least "minimal")

  5. #### Move secrets to env file

  - Put secret values in env/openclaw.env (chmod 600), e.g.:
      - OPENCLAW_GATEWAY_PASSWORD=...
      - Telegram bot token (or use tokenFile)
  - OpenClaw supports ${VAR} substitution in config.

  6. #### Harden Telegram channel

  - Keep Telegram in long-polling mode (default); do not enable webhook.
  - Set strict sender policy:
      - channels.telegram.dmPolicy: "allowlist" (or keep pairing then convert)
      - channels.telegram.allowFrom: ["<your_numeric_user_id>"]
      - channels.telegram.groupPolicy: "disabled" (unless you explicitly need
        groups)
  - Confirm your numeric ID via openclaw logs --follow and from.id.

  7. #### Isolate DM contexts

  - Set session.dmScope: "per-channel-peer" to prevent cross-user/context
    leakage.

  8. #### Reduce tool blast radius before vault

  - Start with sandboxed, no-workspace tool profile:
      - agents.defaults.sandbox.mode: "all"
      - agents.defaults.sandbox.scope: "agent"
      - agents.defaults.sandbox.workspaceAccess: "none"
  - Use tool allow/deny so untrusted prompts cannot write/exec by default.

  9. #### Launchd control + versioned plist

  - Ensure service is installed: openclaw gateway install
  - Copy plist to git control repo:
      - ~/Library/LaunchAgents/bot.molt.gateway.plist → launchd/
  - After each reinstall/update, re-copy and diff the plist.

  10. #### Add explicit upgrade playbook (inference)

  - In playbooks/upgrade.md define exact order:
      1. Backup ~/.openclaw/
      2. Update OpenClaw
      3. openclaw doctor
      4. openclaw security audit --deep
      5. openclaw gateway restart
      6. openclaw health
      7. Telegram DM test
      8. Rollback command if failed (npm i -g openclaw@<previous_version>)

  11. #### Pre-vault canary period (recommended)

  - Run 3–7 days with no vault mounted.
  - Pass criteria:
      - no unexpected tool calls
      - no audit criticals
      - stable Telegram ingest/reply
  - Then grant read-only access first; defer write access until stable.

  12. #### Vault access model (recommended)

  - Split agents:
      - Reader agent: read-only vault workspace
      - Writer agent: restricted workspace for Inbox/ notes only
  - This keeps retrieval broad while limiting write risk.

  #### Important note on Telegram security

  - Telegram bots are cloud-chat/server-client encrypted, not Secret Chat E2EE;
    treat bot input as medium-trust, not for highest-sensitivity secrets.

  #### Sources:

  - https://docs.openclaw.ai/gateway/security
  - https://docs.openclaw.ai/web
  - https://docs.openclaw.ai/gateway/configuration
  - https://docs.openclaw.ai/channels/telegram
  - https://docs.openclaw.ai/install/updating
  - https://docs.openclaw.ai/platforms/mac/bundled-gateway
  - https://telegram.org/faq
  - https://docs.brew.sh/Manpage

  If you want, next I can give you a concrete hardened openclaw.json template +
  a matching upgrade.md you can drop into ~/ops/openclaw-control/.