# MediSense AI — BPMN Diagrams

Four BPMN 2.0 process models for the MediSense AI platform, with rendered images.

| # | Process | Mermaid source | BPMN XML | PNG | SVG |
|---|---------|----------------|----------|-----|-----|
| 1 | End-to-end (all actors) | `01-end-to-end.mmd` | `01-end-to-end.bpmn` | `01-end-to-end.png` | `01-end-to-end.svg` |
| 2 | Patient chat with RAG | `02-chat-rag.mmd` | `02-chat-rag.bpmn` | `02-chat-rag.png` | `02-chat-rag.svg` |
| 3 | Appointment + no-show + CRM | `03-appointment-noshow.mmd` | `03-appointment-noshow.bpmn` | `03-appointment-noshow.png` | `03-appointment-noshow.svg` |
| 4 | IoT ingestion → anomaly → DPA | `04-iot-anomaly-dpa.mmd` | `04-iot-anomaly-dpa.bpmn` | `04-iot-anomaly-dpa.png` | `04-iot-anomaly-dpa.svg` |

## Opening BPMN files

- **bpmn.io** — drag the `.bpmn` file onto https://demo.bpmn.io
- **Camunda Modeler** — https://camunda.com/download/modeler/
- **draw.io / diagrams.net** — File → Open → choose `.bpmn`

The BPMN files contain both the semantic process (tasks, gateways, sequence flows) and a basic BPMN-DI layout. Modelers will auto-improve the layout on open.

## Re-rendering the PNGs/SVGs

```bash
cd docs/bpmn
for f in 01-end-to-end 02-chat-rag 03-appointment-noshow 04-iot-anomaly-dpa; do
  npx -y -p @mermaid-js/mermaid-cli mmdc -i ${f}.mmd -o ${f}.png -b white
  npx -y -p @mermaid-js/mermaid-cli mmdc -i ${f}.mmd -o ${f}.svg -b white
done
```

## Source mapping

| BPMN element | Code reference |
|---|---|
| Auth flow | `backend/app/api/v1/endpoints/auth.py:39` |
| Chat / RAG pipeline | `backend/app/api/v1/endpoints/chat.py:50`, `backend/app/rag/pipeline.py:51` |
| Safety pre/post check | `backend/app/rag/safety.py` |
| Appointment booking | `backend/app/api/v1/endpoints/appointments.py:128` |
| No-show predictor (XGBoost) | `backend/app/services/noshow_predictor.py:53` |
| CRM (Salesforce) | `backend/app/services/salesforce_client.py`, `backend/app/api/v1/endpoints/crm.py` |
| Kafka IoT consumer | `backend/app/services/kafka_consumer.py:88` |
| Anomaly detector (LSTM) | `backend/app/services/anomaly_detector.py:41` |
| DPA review | `backend/app/api/v1/endpoints/doctor.py:56` |
| Audit logs | `backend/app/core/audit.py`, `backend/app/api/v1/endpoints/admin.py:39` |
