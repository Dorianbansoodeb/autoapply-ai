# Site compliance

Unknown policy means assisted mode only: the agent may fill, and you click
Submit.

| Site | How a job gets in | Fill behavior | Mode |
|---|---|---|---|
| Greenhouse | Public board JSON (`boards-api.greenhouse.io`) | Generic label/role filler on the hosted form | B until you review the site and it earns C |
| Lever | Public postings JSON (`api.lever.co`) | Generic filler | B until reviewed and earned |
| Ashby | Public job-board JSON (`api.ashbyhq.com`) | Generic filler | B until reviewed and earned |
| Workday | You paste the tenant URL. No public job API | `data-automation-id` adapter. Email and a generated keychain password are prefilled at signup. Create Account and email verification are yours | B only |
| Anything else | You paste the URL | Assisted fill, stop before Submit | B only |

The agent does not bypass CAPTCHA, MFA, bot checks, or access controls. It
does not read an inbox. It does not complete employer assessments or timed
tests. Read the employer's terms before you apply. Promoting a site
(`autoapply policy review URL`) only allowlists it for later promotion after
20 clean runs; Workday cannot be promoted.
