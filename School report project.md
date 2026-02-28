You should collect information about primary schools and secondary schools from ofsted website. focus on London and surrounding commuter towns (e.g. Surrey)

collect all the information you can find from ofsted. collect metadata as well and store the data in line with best practices of relational databases and use metadata to make the fields easy to understand.

---

## Data sources

All files are downloaded automatically by the pipeline scripts except where noted.

| Dataset | Source page | Direct download URL |
|---------|-------------|---------------------|
| Ofsted latest inspections (monthly CSV) | https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes | Auto-detected by `fetch_ofsted_data.py` (scrapes the page for the latest CSV link) |
| KS2 attainment 2024/25 (primary) | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/b361b4c3-21b9-46fd-9126-b8060c6a40e2 | `https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/b361b4c3-21b9-46fd-9126-b8060c6a40e2/csv` |
| KS4 performance 2023/24 (secondary) | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/c8f753ef-b76f-41a3-8949-13382e131054 | `https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/c8f753ef-b76f-41a3-8949-13382e131054/csv` |
| Pupil absence 2023/24 | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/1ef1689a-070a-4e0b-9314-512db23a3cc9 | `https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/1ef1689a-070a-4e0b-9314-512db23a3cc9/csv` |
| Exclusions & suspensions 2023/24 | https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/6ffc5087-5f61-47a1-9086-d1c374039d1b | `https://explore-education-statistics.service.gov.uk/data-catalogue/data-set/6ffc5087-5f61-47a1-9086-d1c374039d1b/csv` |
| School applications & offers 2024/25 | https://explore-education-statistics.service.gov.uk (school-level file) | **Manually downloaded** — saved as `data/AppsandOffers_2024_SchoolLevel.csv` |

---

## Report webpage

Live URL: https://qiaohong.github.io/school-report/report.html

The report is a self-contained HTML file generated from the SQLite database and hosted on GitHub Pages.

### How to update the webpage

```bash
cd "/root/my-vault/school selector"

# 1. Regenerate the HTML from the latest database
venv/bin/python generate_report.py

# 2. Commit and push — GitHub Pages updates within ~1 minute
git add report.html
git commit -m "Update report"
git push
```
