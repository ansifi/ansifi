# Ansif P. Ibrahimkutty

**Enterprise Systems Architect** · **Studio Founder, [Sevendyne](https://www.sevendyne.com)** · **20+ years** in full-stack design and high-performance application engineering.

I architect **C++/Qt6 embedded systems**, **high-concurrency data pipelines**, and **production enterprise platforms** for regulated, multi-tenant environments. Since 2016 I lead governed engineering programmes through Sevendyne — UK, Germany, Malaysia, Singapore, Indonesia, and UAE clients — while this profile documents **delivery patterns and programme proof** from two decades of hands-on work.

**Technical proof:** [github.com/ansifi](https://github.com/ansifi) · **Programmes delivered:** [sevendyne.com/case-studies](https://www.sevendyne.com/case-studies/)

---

## Programmes & delivery proof

| Domain | What was shipped | Case study |
| :--- | :--- | :--- |
| **Logistics & field sync** | Laravel/Vue pod; queue workers cleared cross-border freight deadlocks; stable web, desktop, and mobile telemetry | [TLMS — Malaysia & Singapore](https://www.sevendyne.com/case-studies/logistics-management-system.html) |
| **Fintech / APAC payments** | Multi-tenant CodeIgniter CRM, payment adapters, Android QR commerce — daily production in Singapore & Indonesia | [PayU CRM & payments](https://www.sevendyne.com/case-studies/custom-crm-payments-platform.html) |
| **AI-assisted recruitment** | Zoho Recruit deep customization + Python/OpenAI workflows with human review — German operator patterns | [Zoho Recruit automation](https://www.sevendyne.com/case-studies/recruitment-automation-zoho.html) |
| **Enterprise analytics** | Angular, Spring Boot, Apache eCharts reporting — transactional vs analytics separation on live data | [German analytics platform](https://www.sevendyne.com/case-studies/enterprise-analytics-platform.html) |
| **Desktop trading / Qt** | C++/Qt and Wt operator desks; market-data presentation; adapter boundaries on proprietary feeds | [Trading System API](https://www.sevendyne.com/case-studies/trading-system-api.html) |
| **Dedicated client teams** | UK automotive PLC/SCADA bench (BMW, Land Rover); German embedded navigation C++ under client product leadership | [UK automotive team](https://www.sevendyne.com/case-studies/uk-automotive-industrial-team.html) · [German navigation C++](https://www.sevendyne.com/case-studies/german-navigation-cpp-team.html) |

Full index: **[sevendyne.com/case-studies](https://www.sevendyne.com/case-studies/)** — engineering pods and dedicated teams since 2016.

---

## Architectural write-ups

Condensed from production delivery. Each programme states **client constraint → engineering response → outcome**.

### Cross-border logistics — TLMS (Malaysia & Singapore)

**The bottleneck:** A shipping operator could not clear data-sync backlogs — field apps and core databases lost packets during high-frequency cross-border freight.

**The response:** Sevendyne-led Laravel/Vue pod re-architected the transaction backend with **async queue workers** — deadlocks cleared, field-to-core sync restored with full telemetry across web, desktop, and mobile.

**Stack:** Laravel · Vue.js · MySQL · REST APIs · queue workers.

**Proof:** [TLMS case study](https://www.sevendyne.com/case-studies/logistics-management-system.html)

---

### Zoho Recruit AI automation (Germany)

**The bottleneck:** German recruiters spent hours on manual Zoho Recruit steps — enrichment, screening, and gaps off-the-shelf configuration could not fix.

**The response:** Deep Zoho Recruit customization plus **Python + OpenAI automation** with operator-visible controls and human review in the loop — idempotent imports and governed workflow gates.

**Stack:** Zoho APIs · Python · OpenAI · SQL warehouse.

**Proof:** [Recruitment automation case study](https://www.sevendyne.com/case-studies/recruitment-automation-zoho.html)

---

### Custom CRM & payments — PayU APAC

**The bottleneck:** PayU-group platforms in Singapore and Indonesia needed one **tenant-safe** CRM and payment stack — wallet, merchant, and logistics had outgrown separate systems.

**The response:** Multi-tenant CodeIgniter/PHP operations, payment adapters, and Android/web QR commerce — staged rollout with backward compatibility for live traffic.

**Stack:** PHP/CodeIgniter · Android · multi-tenant REST · payment adapters.

**Proof:** [CRM & payments case study](https://www.sevendyne.com/case-studies/custom-crm-payments-platform.html)

---

### Embedded Qt6 — IVI / HMI (Panasonic, Cobham)

**The bottleneck:** Video and telemetry decoders feed QML surfaces on resource-constrained SoCs. Naive threading stalls the render loop or causes torn frames.

**The response:** Hard-separate **decode/worker threads** from the Qt Quick render thread; bounded buffers with back-pressure; QML for presentation only — control logic and protocol adapters in C++ with documented contracts. Delivered on **Panasonic** and **Cobham** IVI programmes and defence HMI on **Wayland Linux** (HCL Technologies, 2014–2015).

**Stack:** Qt6 · QML · C++ · Wayland · embedded Linux · automotive / defence HMI.

---

### Protocol & hardware operator consoles (HexoSys)

**The bottleneck:** Firmware teams need repeatable USB/DDR and TCP/UDP validation against embedded targets; silent retries hide hardware faults.

**The response:** Qt/VC++ operator UI with **observable send/receive states** — protocol adapters isolated from widget trees so test harnesses replay without UI churn. Delivered at **HexoSys SDN BHD**, Malaysia (2009–2011).

**Stack:** Qt · VC++ · USB · TCP/UDP · firmware-adjacent tooling.

---

### Desktop trading & market-data surfaces

**The bottleneck:** Operator dashboards need low-latency chart and feed refresh without coupling market-data adapters into presentation widgets.

**The response:** Native Qt/C++ and Wt stacks with **adapter boundaries** — feeds normalize upstream; widgets consume stable view models. Foundational Sevendyne Qt delivery (2016–2018); extended in client trading programmes.

**Stack:** Qt · C++ · Wt · market-data integration · desktop operator UI.

**Proof:** [Trading System API](https://www.sevendyne.com/case-studies/trading-system-api.html)

---

## Professional experience

*Reverse chronological. Pre-2016 roles are direct employment or independent delivery; Sep 2016 onward includes Sevendyne-founded programmes.*

| Period | Role · organisation | Highlights |
| :--- | :--- | :--- |
| **2016 – present** | **Co-founder · Principal Architect** · [Sevendyne](https://www.sevendyne.com) | Engineering pods, dedicated client teams, India payroll & compliance for UK, Germany, UAE, US clients |
| **2022 – 2024** | Remote full-stack · **CSR Informatics**, Germany | Zoho/OpenAI recruitment automation; Rails/Python data pipelines; Angular/Spring/eCharts analytics |
| **2019 – 2022** | Remote full-stack · **Niaga Prestasi**, Malaysia | PayU CRM & payments; TLMS logistics; tokenised property (React, Node, Web3) |
| **2016 – 2018** | C++/Qt · **TradingSystemAPI** | Trading desk UI — Qt, Wt, proprietary library integration |
| **2015 – 2016** | C++/Wt · **Wise Owl** | Property-management web admin |
| **2014 – 2015** | C++/Qt · **HCL Technologies** | Panasonic & Cobham IVI; defence HMI on Wayland |
| **2013 – 2014** | C++/Qt · **Montal** | 2D game UI — Qt/QML |
| **2012** | .NET · **Quality Education Holdings**, Saudi Arabia | Fingerprint verification & attendance systems |
| **2009 – 2011** | C++ · **HexoSys**, Malaysia | USB protocol tester; TCP/UDP validation consoles |
| **2008 – 2009** | Junior C++ · **Pramura**, **UCI** | Product and tooling deliverables |
| **2007 – 2008** | Trainee C++ · **Integralsoft** | PathModeler USB modelling; trading-room utilities |

**Education:** B.E. Computer Science · TKM College of Engineering, Kerala University · 2002–2006

---

## Engineering scope

| Domain | Technologies |
| :--- | :--- |
| Embedded & desktop systems | Qt6, QML, C++, VC++, Wt, Wayland, embedded Linux |
| Concurrency & data paths | Thread sync, buffer pipelines, queue workers, adapter isolation |
| Enterprise web & APIs | Laravel, Vue, Angular, Spring Boot, PHP/CodeIgniter, React, Node.js, REST, Web3 |
| Operations & AI-assisted workflows | Zoho APIs, Python, OpenAI orchestration, SQL reporting, human-in-loop gates |

---

## Connect

| Platform | Link |
| :--- | :--- |
| **Enterprise programmes & contact** | [sevendyne.com/contact](https://www.sevendyne.com/contact/) · [Book 30 min](https://calendly.com/sevendyne/30min) |
| **Case studies** | [sevendyne.com/case-studies](https://www.sevendyne.com/case-studies/) |
| **Long-form writing** | [ansifpi.medium.com](https://ansifpi.medium.com) |
| **LinkedIn** | [linkedin.com/in/ansifpi](https://www.linkedin.com/in/ansifpi/) |
| **X** | [x.com/anspi07](https://x.com/anspi07) |
| **Facebook** | [facebook.com/anspi07](https://www.facebook.com/anspi07) |
| **Instagram** | [instagram.com/ansifktm](https://www.instagram.com/ansifktm/) |
| **Discord** | `@anspi07` |

---

*This repository is the GitHub profile README only. Governed client delivery, team models, and full programme detail live at **[Sevendyne](https://www.sevendyne.com)**.*
