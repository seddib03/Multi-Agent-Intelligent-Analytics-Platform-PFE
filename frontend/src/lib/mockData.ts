import type { Sector, ColumnMetadata, Entity, ChartData } from "@/types/app";

export function detectSector(description: string): Sector {
  const d = description.toLowerCase();
  if (/machine|panne|température|vibration|maintenance|capteur|usine/.test(d)) return "manufacturing";
  if (/retard|route|véhicule|transport|livraison|logistique|trajet/.test(d)) return "transport";
  if (/citoyen|dossier|service public|administration|collectivité/.test(d)) return "public";
  if (/magasin|panier|achat|produit|stock|retail|boutique/.test(d)) return "retail";
  return "finance";
}

const SECTOR_COLUMNS: Record<Sector, ColumnMetadata[]> = {
  finance: [
    { originalName: "customer_id", businessName: "ID Client", semanticType: "identifier", unit: "", missingPercent: 0 },
    { originalName: "age", businessName: "Âge", semanticType: "numeric", unit: "ans", missingPercent: 2 },
    { originalName: "tenure", businessName: "Ancienneté", semanticType: "numeric", unit: "mois", missingPercent: 0 },
    { originalName: "monthly_charges", businessName: "Charges mensuelles", semanticType: "numeric", unit: "€", missingPercent: 1 },
    { originalName: "total_charges", businessName: "Charges totales", semanticType: "numeric", unit: "€", missingPercent: 3 },
    { originalName: "contract_type", businessName: "Type de contrat", semanticType: "category", unit: "", missingPercent: 0 },
    { originalName: "payment_method", businessName: "Mode de paiement", semanticType: "category", unit: "", missingPercent: 0 },
    { originalName: "last_login", businessName: "Dernière connexion", semanticType: "date", unit: "", missingPercent: 8 },
    { originalName: "support_tickets", businessName: "Tickets support", semanticType: "numeric", unit: "", missingPercent: 0 },
    { originalName: "num_products", businessName: "Nb produits", semanticType: "numeric", unit: "", missingPercent: 0 },
    { originalName: "satisfaction_score", businessName: "Score satisfaction", semanticType: "numeric", unit: "/10", missingPercent: 5 },
    { originalName: "churn", businessName: "Churn", semanticType: "target", unit: "", missingPercent: 0 },
  ],
  transport: [
    { originalName: "route_id", businessName: "ID Route", semanticType: "identifier", unit: "", missingPercent: 0 },
    { originalName: "departure_time", businessName: "Heure départ", semanticType: "date", unit: "", missingPercent: 1 },
    { originalName: "arrival_time", businessName: "Heure arrivée", semanticType: "date", unit: "", missingPercent: 2 },
    { originalName: "distance_km", businessName: "Distance", semanticType: "numeric", unit: "km", missingPercent: 0 },
    { originalName: "vehicle_type", businessName: "Type véhicule", semanticType: "category", unit: "", missingPercent: 0 },
    { originalName: "weather", businessName: "Météo", semanticType: "category", unit: "", missingPercent: 3 },
    { originalName: "traffic_index", businessName: "Indice trafic", semanticType: "numeric", unit: "", missingPercent: 4 },
    { originalName: "delay_minutes", businessName: "Retard", semanticType: "target", unit: "min", missingPercent: 0 },
  ],
  retail: [
    { originalName: "client_id", businessName: "ID Client", semanticType: "identifier", unit: "", missingPercent: 0 },
    { originalName: "purchase_date", businessName: "Date achat", semanticType: "date", unit: "", missingPercent: 0 },
    { originalName: "basket_value", businessName: "Panier moyen", semanticType: "numeric", unit: "€", missingPercent: 1 },
    { originalName: "category", businessName: "Catégorie", semanticType: "category", unit: "", missingPercent: 0 },
    { originalName: "return_rate", businessName: "Taux retour", semanticType: "numeric", unit: "%", missingPercent: 2 },
    { originalName: "loyalty_score", businessName: "Score fidélité", semanticType: "target", unit: "/100", missingPercent: 0 },
  ],
  manufacturing: [
    { originalName: "machine_id", businessName: "ID Machine", semanticType: "identifier", unit: "", missingPercent: 0 },
    { originalName: "timestamp", businessName: "Horodatage", semanticType: "date", unit: "", missingPercent: 0 },
    { originalName: "temperature", businessName: "Température", semanticType: "numeric", unit: "°C", missingPercent: 1 },
    { originalName: "vibration", businessName: "Vibration", semanticType: "numeric", unit: "mm/s", missingPercent: 2 },
    { originalName: "pressure", businessName: "Pression", semanticType: "numeric", unit: "bar", missingPercent: 0 },
    { originalName: "operating_hours", businessName: "Heures opération", semanticType: "numeric", unit: "h", missingPercent: 0 },
    { originalName: "failure", businessName: "Panne", semanticType: "target", unit: "", missingPercent: 0 },
  ],
  public: [
    { originalName: "dossier_id", businessName: "ID Dossier", semanticType: "identifier", unit: "", missingPercent: 0 },
    { originalName: "submission_date", businessName: "Date soumission", semanticType: "date", unit: "", missingPercent: 0 },
    { originalName: "service_type", businessName: "Type service", semanticType: "category", unit: "", missingPercent: 0 },
    { originalName: "complexity", businessName: "Complexité", semanticType: "numeric", unit: "/5", missingPercent: 3 },
    { originalName: "processing_days", businessName: "Durée traitement", semanticType: "target", unit: "jours", missingPercent: 0 },
    { originalName: "satisfaction", businessName: "Satisfaction", semanticType: "numeric", unit: "/10", missingPercent: 5 },
  ],
};

export function getColumnsForSector(sector: Sector): ColumnMetadata[] {
  return SECTOR_COLUMNS[sector];
}

export function generatePreviewData(columns: ColumnMetadata[], rows: number = 5): Record<string, unknown>[] {
  const data: Record<string, unknown>[] = [];
  for (let i = 0; i < rows; i++) {
    const row: Record<string, unknown> = {};
    columns.forEach((col) => {
      switch (col.semanticType) {
        case "identifier": row[col.originalName] = `${col.originalName.toUpperCase().slice(0, 3)}-${1000 + i}`; break;
        case "date": row[col.originalName] = `2025-0${(i % 9) + 1}-${10 + i}`; break;
        case "numeric": row[col.originalName] = Math.round(Math.random() * 100 * 10) / 10; break;
        case "category": {
          const cats = ["A", "B", "C", "Premium", "Standard"];
          row[col.originalName] = cats[i % cats.length];
          break;
        }
        case "target": row[col.originalName] = i % 3 === 0 ? 1 : 0; break;
        default: row[col.originalName] = `val_${i}`;
      }
    });
    data.push(row);
  }
  return data;
}

export function generateEntities(sector: Sector): Entity[] {
  const names: Record<Sector, string[]> = {
    finance: ["Marie Dupont", "Jean Martin", "Sophie Bernard", "Lucas Petit", "Emma Robert", "Hugo Durand", "Léa Simon", "Thomas Laurent"],
    transport: ["Route A1-Nord", "Ligne 42", "Express Sud", "Navette Centre", "Route B7", "Liaison Ouest", "Express 15", "Route C3"],
    retail: ["Client VIP-001", "Famille Martin", "Fidèle-Gold-22", "Premium-18", "Client-Regular-55", "VIP-033", "Nouveau-88", "Fidèle-12"],
    manufacturing: ["Machine CNC-01", "Presse HYD-03", "Robot ASM-12", "Tour NUM-05", "Soudeuse ARC-07", "Fraiseuse CNC-08", "Presse INJ-02", "Convoyeur BLT-04"],
    public: ["Dossier URB-2024", "Demande SOC-887", "Dossier ENV-123", "Requête FIN-456", "Dossier HAB-789", "Plainte SRV-321", "Demande CUL-654", "Dossier TRA-987"],
  };
  const factors: Record<Sector, string[]> = {
    finance: ["Ancienneté faible", "Charges élevées", "Nb tickets élevé", "Score satisfaction bas"],
    transport: ["Trafic dense", "Météo dégradée", "Distance longue", "Véhicule ancien"],
    retail: ["Fréquence basse", "Panier en baisse", "Retours fréquents", "Inactif 60j+"],
    manufacturing: ["Vibration anormale", "Température élevée", "Heures excessives", "Pression instable"],
    public: ["Complexité haute", "Pièces manquantes", "Service surchargé", "Délai dépassé"],
  };

  return names[sector].map((name, i) => ({
    id: `E-${1000 + i}`,
    name,
    riskScore: Math.round((95 - i * 7 + Math.random() * 5) * 10) / 10,
    mainFactor: factors[sector][i % factors[sector].length],
    trend: i % 3 === 0 ? "up" : i % 3 === 1 ? "down" : "stable",
  }));
}

export function generateFeatureImportance(columns: ColumnMetadata[]): { feature: string; importance: number }[] {
  return columns
    .filter((c) => c.semanticType !== "identifier" && c.semanticType !== "target" && c.semanticType !== "ignore")
    .map((c) => ({
      feature: c.businessName,
      importance: Math.round(Math.random() * 40 + 5),
    }))
    .sort((a, b) => b.importance - a.importance);
}

export const SECTOR_LABELS: Record<Sector, { icon: string; label: string }> = {
  finance: { icon: "🏦", label: "Finance" },
  transport: { icon: "🚛", label: "Transport" },
  retail: { icon: "🛍️", label: "Retail" },
  manufacturing: { icon: "🏭", label: "Manufacturing" },
  public: { icon: "🏛️", label: "Service Public" },
};

export const SECTOR_KPIS: Record<Sector, { key: string; label: string; value: string; variation: number }[]> = {
  finance: [
    { key: "at_risk", label: "Clients à risque", value: "3 847", variation: 12.3 },
    { key: "churn_rate", label: "Taux de churn prédit", value: "9.1%", variation: -2.1 },
    { key: "revenue", label: "Revenu menacé", value: "€ 284 K", variation: 8.7 },
    { key: "retention", label: "Score de rétention", value: "78/100", variation: 3.2 },
    { key: "ltv", label: "LTV moyen", value: "€ 1 240", variation: -1.5 },
    { key: "nps", label: "NPS Score", value: "42", variation: 5.1 },
    { key: "tickets", label: "Tickets ouverts", value: "234", variation: -15 },
    { key: "conversion", label: "Taux conversion", value: "23%", variation: 4.2 },
  ],
  transport: [
    { key: "delays", label: "Retards prévus", value: "127", variation: -8.3 },
    { key: "critical_routes", label: "Routes critiques", value: "8", variation: 2 },
    { key: "reliability", label: "Score fiabilité", value: "86%", variation: 1.2 },
    { key: "incidents", label: "Incidents prévus", value: "14", variation: -5 },
    { key: "fuel", label: "Coût carburant", value: "€ 18 K", variation: 3.8 },
    { key: "utilization", label: "Taux utilisation", value: "91%", variation: 2.1 },
  ],
  retail: [
    { key: "at_risk", label: "Clients à risque", value: "2 134", variation: 5.3 },
    { key: "basket", label: "Panier moyen prédit", value: "€ 67", variation: -3.2 },
    { key: "return_rate", label: "Taux retour prévu", value: "12%", variation: 1.8 },
    { key: "loyalty", label: "Score fidélité", value: "71/100", variation: -2.1 },
    { key: "stock", label: "Ruptures prévues", value: "23", variation: -12 },
    { key: "revenue", label: "CA prévu", value: "€ 1.2 M", variation: 4.5 },
  ],
  manufacturing: [
    { key: "machines", label: "Machines à risque", value: "7", variation: 2 },
    { key: "failures", label: "Pannes prévues", value: "3", variation: -1 },
    { key: "cost", label: "Coût maintenance", value: "€ 42 K", variation: 5.2 },
    { key: "availability", label: "Disponibilité", value: "94%", variation: 1.3 },
    { key: "oee", label: "OEE", value: "87%", variation: 2.4 },
    { key: "mtbf", label: "MTBF", value: "342h", variation: -3.1 },
  ],
  public: [
    { key: "dossiers", label: "Dossiers à risque", value: "512", variation: -3.1 },
    { key: "delay", label: "Délai moyen prédit", value: "18 jours", variation: 2.5 },
    { key: "escalations", label: "Escalades prévues", value: "89", variation: -7.2 },
    { key: "satisfaction", label: "Satisfaction", value: "72%", variation: 1.8 },
    { key: "backlog", label: "Backlog", value: "1 234", variation: -5 },
    { key: "processing", label: "En traitement", value: "678", variation: 3 },
  ],
};

export function getSuggestedQuestions(sector: Sector): string[] {
  const questions: Record<Sector, string[]> = {
    finance: [
      "Quels sont les 10 clients les plus à risque de churn ?",
      "Quels facteurs influencent le plus le churn ?",
      "Quelle est l'évolution du taux de churn sur 90 jours ?",
      "Quel segment client a le plus fort risque ?",
    ],
    transport: [
      "Quelles routes auront le plus de retards demain ?",
      "Quel est l'impact de la météo sur les délais ?",
      "Quels véhicules nécessitent une maintenance ?",
      "Quelle est la tendance des incidents par semaine ?",
    ],
    retail: [
      "Quels clients risquent de ne plus revenir ?",
      "Quels produits ont le plus fort taux de retour ?",
      "Comment évolue le panier moyen par segment ?",
      "Quelles catégories surperforment ce mois ?",
    ],
    manufacturing: [
      "Quelles machines risquent une panne cette semaine ?",
      "Quel capteur détecte le mieux les anomalies ?",
      "Quelle est la tendance de disponibilité par ligne ?",
      "Quel est le coût prédit de maintenance ce mois ?",
    ],
    public: [
      "Quels dossiers risquent un dépassement de délai ?",
      "Quel service a le taux d'escalade le plus élevé ?",
      "Comment évolue la satisfaction citoyenne ?",
      "Quelles sont les causes principales de retard ?",
    ],
  };
  return questions[sector];
}

export function generateMockResponse(question: string, sector: Sector): { text: string; charts: ChartData[]; predictions: Entity[] } {
  const text = `Voici l'analyse de votre question. Sur la base de **${sector === "finance" ? "42 312 clients" : sector === "transport" ? "8 450 trajets" : sector === "retail" ? "15 230 clients" : sector === "manufacturing" ? "156 machines" : "3 890 dossiers"}** analysés, le modèle **XGBoost** (AUC: **0.871**) identifie des patterns significatifs.\n\nLes facteurs clés sont **${sector === "finance" ? "l'ancienneté" : sector === "transport" ? "l'indice trafic" : "le score fidélité"}** et **${sector === "finance" ? "les charges mensuelles" : sector === "transport" ? "la distance" : "la fréquence d'achat"}** qui expliquent ensemble **67%** de la variance observée.`;

  const charts: ChartData[] = [
    {
      type: "bar",
      title: "Importance des facteurs",
      data: [
        { name: "Facteur 1", value: 38 },
        { name: "Facteur 2", value: 29 },
        { name: "Facteur 3", value: 18 },
        { name: "Facteur 4", value: 10 },
        { name: "Facteur 5", value: 5 },
      ],
      dataKeys: ["value"],
    },
    {
      type: "line",
      title: "Évolution temporelle",
      data: Array.from({ length: 7 }, (_, i) => ({
        name: `S${i + 1}`,
        actuel: Math.round(Math.random() * 30 + 60),
        prédit: Math.round(Math.random() * 30 + 55),
      })),
      dataKeys: ["actuel", "prédit"],
    },
  ];

  return { text, charts, predictions: generateEntities(sector).slice(0, 5) };
}
