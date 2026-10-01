File by business function in an intermediate category or X. A parent grant includes current and future children.

| Code | Category | Parent | Scope |
|---|---|---|---|
| `C-corporate` | Corporate | — | Legal entity, ownership and corporate decisions. |
| `CR-registration` | Registration | C | Formation, articles, registrations and legal entity records. |
| `CO-ownership` | Ownership | C | Shareholder registers, capitalization tables and ownership records. |
| `CG-governance` | Governance | C | Board and shareholder decisions, minutes and delegated authorities. |
| `H-human-resources` | Human resources | — | Employment, organization and employee records. |
| `HO-organization` | Organization | H | Organization charts, job descriptions and aggregate workforce information. |
| `HP-policies` | Employment policies | H | Employment rules, benefits policies and employee handbooks. |
| `HE-employment` | Employment records | H | Individual employment agreements, onboarding, leave and departure records. Payroll payments belong to FP. |
| `HR-recruiting` | Recruiting | H | Job postings, applications and hiring records. |
| `HA-appraisals` | Appraisals | H | Individual performance, disciplinary and development records. |
| `F-finance` | Finance | — | Financial position, accounting, tax and payments. |
| `FS-statements` | Financial statements | F | Financial statements, financial audit reports and consolidated results. Supporting accounting evidence belongs to FA. |
| `FB-budgets` | Budgets | F | Budgets, financial forecasts and financial models. |
| `FT-tax` | Tax | F | Tax returns, assessments and tax authority correspondence. Employee withholding belongs to FP. |
| `FC-cash` | Cash and banking | F | Bank statements, payments, treasury and account documentation. Excludes credentials and financing agreements, which belong to RA. |
| `FA-accounting` | Accounting evidence | F | Ledgers, invoices, receipts and accounting evidence. Underlying contracts follow the relationship. |
| `FP-payroll` | Payroll | F | Payroll registers, payslips, payroll calculations and employee tax withholding. Employment terms belong to HE. |
| `S-sales` | Sales and marketing | — | Customers, commercial partnerships and market-facing work. |
| `SS-sales` | Sales materials | S | Proposals, quotes, sales materials and commercial analysis. Fundraising presentations belong to RP. |
| `SM-marketing` | Marketing | S | Brand assets, campaigns, advertising and market research, including images and video. |
| `SC-customers` | Customer records | S | Customer agreements, orders, correspondence and service records. Invoice originals belong to FA. |
| `SP-partners` | Commercial partners | S | Distribution, referral and commercial partnership records. Procurement belongs to OS. |
| `P-product` | Products and services | — | What the company delivers to customers. |
| `PO-overview` | Product overview | P | Product and service descriptions, catalogs and user-facing manuals. Persuasive sales materials belong to SS. |
| `PD-development` | Development | P | Specifications, designs, architecture, roadmaps and development records. |
| `PQ-quality` | Quality | P | Testing, quality control, defects and acceptance records. Formal certifications belong to LC. |
| `O-operations` | Operations | — | Operating the company, facilities, procurement and internal systems. |
| `OP-procedures` | Operating procedures | O | Internal operating procedures and continuity plans. Employment rules belong to HP and security policies to LS. |
| `OA-assets` | Assets and facilities | O | Asset registers, premises, leases, equipment and maintenance records. |
| `OS-suppliers` | Suppliers | O | Procurement, supplier agreements, correspondence and supply-chain records. |
| `OI-it` | Internal IT | O | Internal IT administration, software subscriptions and routine incidents. Security incidents belong to LS. Never store credentials. |
| `I-ip` | Intellectual property | — | Ownership, registration and licensing of intellectual property. |
| `IR-rights` | IP rights | I | Patents, trademarks, copyright ownership and intellectual property registrations. |
| `IL-licenses` | IP licenses | I | Grants, assignments and acquisition of IP rights. Routine software subscriptions belong to OI. |
| `L-legal` | Legal and compliance | — | Legal obligations, regulation and risk. |
| `LC-compliance` | Regulatory compliance | L | Permits, certifications, regulatory filings and compliance assessments. |
| `LS-security` | Security and privacy | L | Security and privacy policies, assessments and incidents. |
| `LD-disputes` | Disputes | L | Claims, litigation, legal opinions and dispute records. |
| `LI-insurance` | Insurance | L | Insurance policies, coverage and claims. |
| `R-fundraising` | Raising capital | — | Raising equity or debt and communicating with capital providers. |
| `RP-presentations` | Financing presentations | R | Fundraising decks and investment or financing narratives. Source financial statements remain in FS. |
| `RA-agreements` | Financing agreements | R | Equity and debt agreements, term sheets and financing negotiations. Resulting ownership registers belong to CO and resolutions to CG. |
| `RR-reporting` | Investor reporting | R | Investor and lender updates and correspondence outside agreement negotiations. |
| `G-general` | General company records | — | Company-wide records outside a specific business function; not miscellaneous storage. |
| `GP-profile` | Company profile | G | Company introductions, history, mission and general company plans. Financing presentations belong to RP. |
| `GC-communications` | Company communications | G | General company announcements and communication records. |
| `GE-events` | Company events | G | Company events and culture records, including event photos and recordings. |
| `X-inbox` | Inbox | — | Unclassified or ambiguous documents. Choose X when context does not identify a destination. Do not invent missing facts. |

## Default roles

Each reader role names an array of category codes. Multiple grants combine. Add custom roles or edit these defaults.

| Role | Name | readableCategories |
|---|---|---|
| `employee` | Employee | [HO, HP, PO, GP, GC, GE] |
| `leadership` | Leadership | [C, H, F, S, P, O, I, L, R, G, X] |
| `finance` | Finance | [CR, F, SC, SP, OA, OS, LI, RA, RR] |
| `people` | People | [CR, H, FP, GP, GC, GE] |
| `investor` | Investor | [CR, CO, FS, FB, PO, RP, RR, GP] |
| `accountant` | Accountant | [CR, F, SC, SP, OA, OS, LI, RA] |
| `legal` | Legal adviser | [C, HP, HE, SC, SP, OA, OS, I, L, RA] |
| `lender` | Lender | [CR, CO, FS, FB, FT, FC, RA, RR, GP] |
