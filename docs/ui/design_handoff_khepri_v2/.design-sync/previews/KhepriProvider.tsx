import * as React from "react";
import { KhepriProvider, Card, Button, StatusPill } from "@khepri/ds";

export const ArabicRoot = () => (
  <KhepriProvider style={{ padding: 20 }}>
    <Card title="البيئة والسياسات العامة" icon="leaf" actions={<StatusPill status="published" />}>
      <p className="k-muted" style={{ marginBottom: 12 }}>تحليل السياسات البيئية وأثرها الاجتماعي والاقتصادي.</p>
      <Button icon="plus">تحليل جديد</Button>
    </Card>
  </KhepriProvider>
);

export const EnglishLtr = () => (
  <KhepriProvider dir="ltr" lang="en" style={{ padding: 20 }}>
    <Card title="Environment & Public Policy" icon="leaf" actions={<StatusPill status="published" label="Published" />}>
      <p className="k-muted" style={{ marginBottom: 12 }}>Environmental policy analysis and its social and economic impact.</p>
      <Button icon="plus">New analysis</Button>
    </Card>
  </KhepriProvider>
);
