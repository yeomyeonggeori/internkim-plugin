# Domains and clearance

| Folder | Domain | Clearance | Holds |
|---|---|---|---|
| `00-public` | public | 0 | published copies: brand, press, certifications, the public deck |
| `01-corporate` | corporate | 1 | articles, registry, business registration |
| `02-governance` | governance | 3 | shareholder register, board minutes, cap table, term sheets, litigation |
| `03-finance` | finance | 2 | statements, audits, budgets, tax, banking |
| `04-contracts` | contracts | 2 | customer, supplier, NDA, lease |
| `05-people` | people | 1 | org chart, work rules, policies |
| `06-hr-records` | hr-records | 3 | employment contracts, payroll, reviews |
| `07-ip` | ip | 1 | patents, trademarks, licences |
| `08-product` | product | 1 | product documents, roadmap, architecture |
| `09-marketing` | marketing | 1 | brand assets, references |
| `10-operations` | operations | 1 | processes, supply chain, facilities |
| `11-compliance` | compliance | 1 | certifications, permits, security policy |
| `12-fundraising` | fundraising | 2 | investor material, investor correspondence |
| `13-media` | media | 1 | photos, video |

| Clearance | Reader |
|---|---|
| 0 | anyone outside the company |
| 1 | every member |
| 2 | management |
| 3 | representative, board |

A member with clearance `n` reads every domain at `n` or below. There is no clearance field on a document: the domain's clearance is the document's. A company adds a domain by naming it and its clearance under `dataroom.domains` in `company.json`.

## Why these domains

The list is the request list a due-diligence team sends before an acquisition or a financing round, which every law firm and audit firm has converged on by running it against hundreds of companies. It is industry-independent, it is where a company's documents end up sorted anyway, and the model already knows which folder an NDA belongs in. It is then cut so that each domain holds one clearance: corporate and people are split into a member-readable domain and a board-readable one, tax joins finance, and the pipeline stays in the CRM tables.

## Placement

A document that belongs to one domain by subject and to another by clearance goes where its clearance is: an acquisition term sheet is governance, an NDA is a contract at clearance 2 though nobody would mind a member reading it. The one error this allows is a document classified higher than it needs, which is the safe direction.

Finance and contracts split by year, media by `photos/<year>` and `videos/<year>`; the rest stay flat. A directory holds forty entries at most. Each domain has an `archive/` the index excludes.
