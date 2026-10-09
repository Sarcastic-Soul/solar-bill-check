# Environmental Hacks (Bharat Builds Tour, Event 02)

All details, copied from the WeMakeDevs site and its API on 2026-10-08.

Sources:
- Overview: https://www.wemakedevs.org/aws/env
- Rules (one rulebook for the whole tour, last updated Sept 16, 2026): https://www.wemakedevs.org/aws/env/rules
- Schedule: https://www.wemakedevs.org/aws/env/schedule
- Mentors: https://www.wemakedevs.org/aws/env/mentors
- Tour home: https://www.wemakedevs.org/aws
- API: https://wemakedevs-server.onrender.com/hackathons/env
- Delhi build day (Luma): https://luma.com/env

## Basics

| | |
|---|---|
| Organizer | WeMakeDevs, in collaboration with AWS Builder Center |
| Tour | Bharat Builds Tour, event 2 of 6 (one tour registration covers all 6) |
| Theme | The environment: bad air, heatwaves, floods, water shortage, waste |
| Format | Hybrid. Online all 4 days, anywhere in India, no cap on numbers. Optional in-person build day in Delhi. |
| Online | Thu Oct 8 to Sun Oct 11, 2026 |
| In person | Sat Oct 10, 8 AM to 8 PM, Delhi Technological University (DTU), Shahbad Daulatpur, Main Bawana Road, Delhi 110042 |
| Team size | 1 to 4 |
| Cost | Free |
| Registered | 8,156 for this event, 22,193 for the whole tour (API, 2026-10-08) |

## Key times (IST)

| What | When | Source |
|---|---|---|
| Start | Thu Oct 8, 08:00 | API `start_date` 2026-10-08T02:30Z |
| Submission form opens | Sun Oct 11, 08:00 | API `submissions_open_at` 2026-10-11T02:30Z |
| **Deadline** | **Sun Oct 11, 20:00** | API `end_date` 2026-10-11T14:30Z, Luma says 8:00 PM IST |
| Results | Not announced | Winners go on the event page and by email |

The schedule page still says "the hours are being finalised" and that everyone checked in is told the same day. Treat 20:00 IST Sunday as the deadline but check the schedule page. **Deadlines are strict: the form closes and nothing gets in after.**

### Schedule

| Day | What |
|---|---|
| Thu Oct 8 | Kickoff. Teams form, tracks get picked, repos get made. |
| Fri Oct 9 | Build, with the community on Discord. |
| Sat Oct 10 | Build. Delhi build day 8 AM to 8 PM (workshops, project feedback, Amazon team). Online carries on as normal. |
| Sun Oct 11 | Last day to submit, demo video included. |

## Prizes

| Prize | Award | Winners |
|---|---|---|
| Track winner: Air | ₹2,00,000 cash + $2,000 AWS credits | 1 team |
| Track winner: Heat and Water | ₹2,00,000 cash + $2,000 AWS credits | 1 team |
| Track winner: Waste and Energy | ₹2,00,000 cash + $2,000 AWS credits | 1 team |
| Runners-up | $1,000 AWS credits per team | 4 teams, from any track, nothing extra to enter |
| Top blogs | AirPods | 5 people. Publish on AWS Builder Center and link it in the submission. |
| Tour swag | The tour kit | "The top teams", number not stated, online or in person |
| Amazon fast-track interview | Skip screening for a 6-month internship or a full-time role | Up to 10 students, picked from all 3 tracks together |
| Certificate | Participation certificate for everyone who submits; winner certificate for winners | All who submit |

- The banner says "₹20 lakh prize pool". The listed prizes add up to ₹6,00,000 cash, $10,000 AWS credits, and 5 AirPods. The site doesn't explain the gap.
- Winning a track does **not** get you a fast-track interview, and winning nothing does **not** rule you out. They are separate decisions made by different people.

## Tracks

Pick the one your project fits best. Each track has its own winner. The listed problems are a starting point, not a fixed list.

1. **Air:** help people breathe easier. AQI, pollution exposure, stubble burning, indoor air, school safety on bad days.
2. **Heat and Water:** heatwaves, floods, monsoon waterlogging, droughts, water tankers, leaks, groundwater.
3. **Waste and Energy:** segregation, recycling, e-waste, informal recyclers, rooftop solar, EV nudges, public transport.

## Two ways to build (any track)

To be eligible for prizes, the project must **use at least one AWS open source tool or be deployed on AWS**. Anything else you use is up to you.

"Build It" and "Ship It" are not prize tracks this time. They are just the two ways to build, and both are scored the same: "We judge what you built, not what you spent."

| Area | Build It (open source, on your machine, no AWS account) | Ship It (deployed on AWS, with a URL) |
|---|---|---|
| Agents and AI | Strands Agents SDK, PartyRock | SageMaker AI |
| Containers and Kubernetes | Finch, EKS Distro, EKS Anywhere | EKS, ECS, Fargate |
| Serverless | SAM CLI, LocalStack | Lambda, API Gateway, Step Functions |
| Servers and runtimes | Firecracker, Corretto | EC2, Lightsail, App Runner, Amplify Hosting |
| Data and search | OpenSearch | S3, DynamoDB, RDS, Aurora |
| Auth and policy | Cedar | Cognito |
| The plumbing | | CloudFront, Route 53, EventBridge, SQS, SNS, CloudWatch |

## AWS credits

- A new AWS account gets up to **$200 in free credits** through the Free Tier, plus the always-free services. Use these first.
- After those run out, request **$25 more** from WeMakeDevs: https://forms.gle/b453U3c63mfBXHVr5. One form per team, filled in by the team leader only (or you, if solo).
- AWS signup accepts debit cards and RuPay. The verification charge is about ₹2.
- Free Tier: https://bit.ly/wmd-aws-free

## Judging criteria

1. **Idea and Impact.** Does it fix a real environmental problem, and what changes for the people living with it? A small problem solved well beats a big one solved vaguely.
2. **Built on AWS.** AWS open source tools locally, or AWS services deployed. **Mandatory to win a prize.**
3. **Design and usability.** Can someone outside your team pick it up and know what to do?
4. **Execution.** Does it work? One feature that runs beats five that almost do.
5. **Demo video.** 3 minutes, recorded: what it does, who it's for, where AWS fits. There is no live demo, so the video is what the judges see.

- Each track is judged on its own.
- Online and in-person projects go to the same panel with the same criteria.
- No weights are published.
- The panel's decision is final. Scores are not published or discussed.

## Official rules (tour rulebook)

### 01 Who can enter
- University students in India, aged 18 or older.
- You need a **WeMakeDevs account** and an **AWS Builder Center profile with your university enrollment verified** (run by SheerID). Verify here: https://bit.ly/abc-verify
- If verification is still pending, enter anyway. You can still submit and be judged. But the Builder Center rewards and the fast-track interview wait on it.
- Register once for the tour, then **check in** to each hackathon when it opens.
- People who run, judge, or work for WeMakeDevs or AWS can take part but cannot win prizes.

### 02 Teams
- Solo, or up to 4 people. Same limit online and in person.
- Teammates can be from different universities and cities. Each must qualify on their own.
- **Every member registers with their own account.** A captain cannot register the rest of the team.
- One submission per team. One team per person per hackathon.
- Part of a team can be at the venue and part online.

### 03 What you build
- Start when the hackathon opens and stop at the deadline. Learning, planning, and practice before the start are fine.
- **Old projects don't count**, even if rewritten.
- Open source libraries, frameworks, public APIs, boilerplate, and starter templates are allowed. Only what you added during the event is judged.
- **Your project must use AWS, and the demo video must show it.** Naming AWS only in the writeup is not enough.
- Free Tier usage counts in full for every track.
- **AI coding tools are allowed. List the ones you used in your writeup.**
- The work must be yours. Anything you didn't write needs a credit and a licence that allows it.
- You keep the rights to your project. WeMakeDevs and AWS may show it and name your team.

### 04 Submissions
A submission is three things:
1. A **public repository**
2. A **demo video, under 3 minutes**, on **YouTube**, set to public or unlisted. Check the link opens in a signed-out browser.
3. A **short writeup**: the problem, the build, and where AWS fits

- Submit once per team on this hackathon's form, before the deadline.
- Judges score only what you submit. If the video doesn't show it, it doesn't count. A feature that exists only in the writeup doesn't count.

### 05 Judging
- See the criteria above.
- **Disqualifies the whole team:** copying someone else's work, passing off an old project as new, or a repo history that doesn't match the event dates.
- Winners are announced on the hackathon page and by email. Prizes go to your registered details, so keep them correct.

### 06 Fast-track interview at Amazon
- Only for **pre-final year (2028) and final year (2027)** students.
- At most **10 per hackathon**. That is a ceiling, not a promise. It can be fewer or none.
- For a 6-month internship or a full-time role.
- Eligibility is checked against your registration and Builder Center profile. Both must be correct, with student status verified, **before** the hackathon you enter.
- Judges, organisers, and Amazon decide. No reasons, no appeal.
- It can be changed, paused, or withdrawn at any time.

Amazon's full terms, in short:
- An interview is not a job offer. You must clear Amazon's normal process.
- It depends on open roles and headcount at the time.
- You must be enrolled in the stated programs with the expected graduation year, meet Amazon's minimum criteria, and have no active disciplinary action.
- Interviews must be taken within the timeframe given, or they lapse.
- No visa, relocation, or pay commitments.
- By taking part you consent to your project and personal info being shared with Amazon's recruiters.
- It applies only to the named people on the selected team and can't be transferred.

### 07 Conduct
- The WeMakeDevs Code of Conduct applies online and in person, in every channel.
- Harassment, cheating, or abuse of mentors, volunteers, or other builders ends your participation. No appeal.
- At the venue, follow the venue's rules and the on-site staff.
- Report anything to the organisers on the day or by email: contact@wemakedevs.org. Reports are handled in confidence.

## Builder Center rewards (verified students)

Verifying your enrollment unlocks $579 of rewards on your profile:
- Skill Builder premium for 1 year ($449)
- A foundational certification voucher ($100)
- Up to $30 in AWS credits, earned through badges

Also on Builder Center: hundreds of hands-on workshops, and free 8-hour AWS sandboxes with no account needed.

## Attending in person (Delhi)

1. Check in on https://www.wemakedevs.org/aws/env first. That enters you online.
2. Then apply for the DTU build day on Luma: https://luma.com/env. Seats are limited and Luma confirms yours by email.

- In person adds **nothing** to your score. Everything judged happens online.
- At DTU: workshops, project feedback, the Amazon team, swag for everyone.
- People there: Kunal Kushwaha (WeMakeDevs), Saiyam Pathak (Kubesimplify), Piyush Garg (Teachyst), plus a team of AWS mentors (cloud, database, and support engineers, account managers, consultants). The full list is on the Mentors page.

## Past event for reference: First Commit (Event 01, Sept 17 to 20, 2026)

- 13,667 registered, 1,180 projects.
- Prizes were ranked, not per track: 1st ₹2L + $3k credits, 2nd ₹1.5L + $2k, 3rd ₹1L + $1k, 4 runners-up at $1k credits each, top 5 blogs got a Logitech keyboard.
- Winners: https://www.wemakedevs.org/aws/first-commit/projects

## Submission checklist

- [ ] Every teammate registered for the tour with their own account and checked in to Environmental Hacks
- [ ] Builder Center profile with student verification (started, at least)
- [ ] Track picked: Air / Heat and Water / Waste and Energy
- [ ] Repo created after the start (Oct 8, 08:00 IST), with commit history inside the event dates
- [ ] Uses at least one AWS open source tool, or is deployed on AWS
- [ ] Demo video under 3 minutes, on YouTube (public or unlisted), shows AWS in use, opens in a signed-out browser
- [ ] Writeup covers the problem, the build, where AWS fits, and lists the AI tools used
- [ ] Credits and licences for anything you didn't write
- [ ] Repo is public
- [ ] Optional: blog on AWS Builder Center, linked in the submission (AirPods prize)
- [ ] Submitted once, before Sun Oct 11, 20:00 IST

## Links

- WeMakeDevs Discord (questions, team-forming channels): https://discord.gg/wemakedevs
- WeMakeDevs space on AWS Builder Center: https://bit.ly/wmd-space
- AWS Builder Center workshops: https://builder.aws.com/workshops
- AWS toolbox: https://builder.aws.com/build/tools
- Questions about the rules: contact@wemakedevs.org ("Ask us before the clock starts, not after.")

## Not found

- How the ₹20 lakh pool is split
- How many teams get swag
- Results date
- Delhi seat count
- Community partners (the page is empty)
