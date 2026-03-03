import type { ColumnMetadata, QualityIssue, Project, Message, ModelResults } from '@/types';

export const mockColumns: ColumnMetadata[] = [
  { originalName: 'customer_id', businessName: 'ID Client', type: 'identifier', unit: '', description: 'Identifiant unique du client', stats: { missing: 0, missingPct: 0, unique: 42312 } },
  { originalName: 'tenure', businessName: 'Ancienneté', type: 'numeric', unit: 'mois', description: 'Durée de la relation client', stats: { missing: 0, missingPct: 0, unique: 72, min: 1, max: 72, mean: 32.4, median: 29, std: 24.6 } },
  { originalName: 'monthly_charges', businessName: 'Charges mensuelles', type: 'numeric', unit: '€', description: 'Montant facturé par mois', stats: { missing: 0, missingPct: 0, unique: 1585, min: 18.25, max: 118.75, mean: 64.76, median: 70.35, std: 30.09 } },
  { originalName: 'total_charges', businessName: 'Charges totales', type: 'numeric', unit: '€', description: 'Montant total facturé', stats: { missing: 247, missingPct: 0.58, unique: 6531, min: 18.8, max: 8684.8, mean: 2283.3, median: 1397.5, std: 2266.8 } },
  { originalName: 'contract_type', businessName: 'Type de contrat', type: 'category', unit: '', description: 'Type de contrat souscrit', stats: { missing: 0, missingPct: 0, unique: 3, topValues: ['Month-to-month', 'Two year', 'One year'] } },
  { originalName: 'internet_service', businessName: 'Service Internet', type: 'category', unit: '', description: 'Type de service internet', stats: { missing: 0, missingPct: 0, unique: 3, topValues: ['Fiber optic', 'DSL', 'No'] } },
  { originalName: 'payment_method', businessName: 'Moyen de paiement', type: 'category', unit: '', description: 'Mode de paiement', stats: { missing: 0, missingPct: 0, unique: 4, topValues: ['Electronic check', 'Mailed check', 'Bank transfer'] } },
  { originalName: 'gender', businessName: 'Genre', type: 'category', unit: '', description: 'Genre du client', stats: { missing: 0, missingPct: 0, unique: 2, topValues: ['Male', 'Female'] } },
  { originalName: 'senior_citizen', businessName: 'Senior', type: 'category', unit: '', description: 'Client senior (65+)', stats: { missing: 0, missingPct: 0, unique: 2, topValues: ['0', '1'] } },
  { originalName: 'partner', businessName: 'Partenaire', type: 'category', unit: '', description: 'A un partenaire', stats: { missing: 0, missingPct: 0, unique: 2, topValues: ['Yes', 'No'] } },
  { originalName: 'dependents', businessName: 'Personnes à charge', type: 'category', unit: '', description: 'A des personnes à charge', stats: { missing: 0, missingPct: 0, unique: 2, topValues: ['No', 'Yes'] } },
  { originalName: 'last_login_days', businessName: 'Dernière connexion', type: 'numeric', unit: 'jours', description: 'Jours depuis dernière connexion', stats: { missing: 3514, missingPct: 8.3, unique: 180, min: 0, max: 365, mean: 42.1, median: 28, std: 51.2 } },
  { originalName: 'support_tickets', businessName: 'Tickets support', type: 'numeric', unit: '', description: 'Nombre de tickets ouverts', stats: { missing: 0, missingPct: 0, unique: 12, min: 0, max: 11, mean: 1.4, median: 1, std: 1.8 } },
  { originalName: 'satisfaction_score', businessName: 'Score satisfaction', type: 'numeric', unit: '/10', description: 'Score NPS', stats: { missing: 892, missingPct: 2.1, unique: 10, min: 1, max: 10, mean: 6.2, median: 6, std: 2.1 } },
  { originalName: 'churn', businessName: 'Churn', type: 'target', unit: '', description: 'Client a résilié', stats: { missing: 0, missingPct: 0, unique: 2, topValues: ['0', '1'] } },
];

export const mockQualityIssues: QualityIssue[] = [
  { id: 'q1', type: 'missing', severity: 'warning', title: 'Valeurs manquantes sur "Dernière connexion"', description: '8.3% de valeurs manquantes sur la colonne last_login_days. Cela peut affecter la qualité des prédictions.', affectedColumns: ['last_login_days'], affectedRows: 3514 },
  { id: 'q2', type: 'duplicates', severity: 'critical', title: '127 lignes dupliquées détectées', description: 'Des lignes identiques ont été trouvées dans le dataset. Cela peut biaiser l\'entraînement du modèle.', affectedColumns: ['all'], affectedRows: 127 },
  { id: 'q3', type: 'outliers', severity: 'warning', title: 'Outliers extrêmes sur "Charges mensuelles"', description: '14 valeurs supérieures à 3 écarts-types détectées sur monthly_charges.', affectedColumns: ['monthly_charges'], affectedRows: 14 },
  { id: 'q4', type: 'imbalance', severity: 'warning', title: 'Variable cible déséquilibrée', description: 'La variable cible est déséquilibrée : 92% classe 0 / 8% classe 1. Cela peut biaiser le modèle.', affectedColumns: ['churn'], affectedRows: 0 },
  { id: 'q5', type: 'correlation', severity: 'info', title: 'Corrélation forte détectée', description: '"tenure" et "total_charges" sont corrélées à 0.94. Considérez supprimer une des deux.', affectedColumns: ['tenure', 'total_charges'], affectedRows: 0 },
  { id: 'q6', type: 'missing', severity: 'info', title: 'Valeurs manquantes sur "Score satisfaction"', description: '2.1% de valeurs manquantes sur satisfaction_score.', affectedColumns: ['satisfaction_score'], affectedRows: 892 },
  { id: 'q7', type: 'missing', severity: 'info', title: 'Valeurs manquantes sur "Charges totales"', description: '0.58% de valeurs manquantes sur total_charges.', affectedColumns: ['total_charges'], affectedRows: 247 },
];

export const mockModelResults: ModelResults = {
  algorithm: 'XGBoost',
  auc: 0.891,
  accuracy: 0.872,
  f1Score: 0.843,
  featureImportance: [
    { feature: 'Type de contrat', importance: 0.28 },
    { feature: 'Ancienneté', importance: 0.22 },
    { feature: 'Charges mensuelles', importance: 0.18 },
    { feature: 'Score satisfaction', importance: 0.12 },
    { feature: 'Dernière connexion', importance: 0.09 },
    { feature: 'Service Internet', importance: 0.06 },
    { feature: 'Tickets support', importance: 0.05 },
  ],
  topRiskyEntities: [
    { id: 'C-4821', name: 'Jean Dupont', risk: 0.94, factors: ['Contrat mensuel', 'Faible satisfaction'] },
    { id: 'C-1293', name: 'Marie Leroy', risk: 0.91, factors: ['120 jours inactif', 'Charges élevées'] },
    { id: 'C-7744', name: 'Pierre Martin', risk: 0.88, factors: ['3 tickets support', 'Contrat mensuel'] },
    { id: 'C-3312', name: 'Sophie Petit', risk: 0.85, factors: ['Nouveau client', 'Fiber optic'] },
    { id: 'C-9012', name: 'Luc Bernard', risk: 0.82, factors: ['Charges > 100€', 'Electronic check'] },
  ],
};

export const sectorSuggestions: Record<string, string[]> = {
  finance: [
    'Quels clients ont le plus grand risque de churn ce mois ?',
    'Quel est le profil type d\'un client qui résilie ?',
    'Quelle est l\'impact du type de contrat sur le churn ?',
    'Prédis le churn pour les 3 prochains mois',
    'Quelles actions réduiraient le churn de 10% ?',
  ],
  transport: [
    'Quels itinéraires présentent le plus de retards ?',
    'Prédis les retards pour la semaine prochaine',
    'Quel est l\'impact de la météo sur les retards ?',
  ],
  retail: [
    'Quels produits recommander à ce segment ?',
    'Prédis les ventes du prochain trimestre',
    'Quel est le panier moyen par segment client ?',
  ],
  manufacturing: [
    'Quelles machines nécessitent une maintenance prochaine ?',
    'Prédis les pannes pour les 30 prochains jours',
    'Quel est le taux de défaut par ligne de production ?',
  ],
  public: [
    'Quels dossiers risquent d\'être en retard ?',
    'Prédis les délais de traitement pour le prochain mois',
    'Quels services sont les plus sollicités ?',
  ],
};

export const mockSampleData = Array.from({ length: 50 }, (_, i) => ({
  customer_id: `C-${1000 + i}`,
  tenure: Math.floor(Math.random() * 72) + 1,
  monthly_charges: +(Math.random() * 100 + 18).toFixed(2),
  total_charges: +(Math.random() * 8000 + 100).toFixed(2),
  contract_type: ['Month-to-month', 'One year', 'Two year'][Math.floor(Math.random() * 3)],
  internet_service: ['Fiber optic', 'DSL', 'No'][Math.floor(Math.random() * 3)],
  payment_method: ['Electronic check', 'Mailed check', 'Bank transfer', 'Credit card'][Math.floor(Math.random() * 4)],
  gender: ['Male', 'Female'][Math.floor(Math.random() * 2)],
  senior_citizen: Math.random() > 0.84 ? 1 : 0,
  partner: ['Yes', 'No'][Math.floor(Math.random() * 2)],
  dependents: ['Yes', 'No'][Math.floor(Math.random() * 2)],
  last_login_days: Math.random() > 0.08 ? Math.floor(Math.random() * 180) : null,
  support_tickets: Math.floor(Math.random() * 6),
  satisfaction_score: Math.random() > 0.02 ? Math.floor(Math.random() * 10) + 1 : null,
  churn: Math.random() > 0.92 ? 1 : 0,
}));

export const mockDemoProjects: Project[] = [
  {
    id: 'proj-1',
    title: 'Prédiction du churn client',
    useCaseDescription: 'Prédire quels clients risquent de résilier leur abonnement dans les 3 prochains mois',
    analysisType: 'classification',
    timeHorizon: '3 mois',
    sector: 'finance',
    status: 'analysis',
    createdAt: '2025-01-15',
    rowCount: 42312,
    columnCount: 15,
    algorithm: 'XGBoost',
    fileName: 'customers.csv',
    qualityScore: 91,
    pipelineProgress: 100,
  },
  {
    id: 'proj-2',
    title: 'Prévision des retards de livraison',
    useCaseDescription: 'Anticiper les retards de livraison basé sur les données historiques et météo',
    analysisType: 'regression',
    timeHorizon: '1 semaine',
    sector: 'transport',
    status: 'ready',
    createdAt: '2025-02-03',
    rowCount: 18450,
    columnCount: 22,
    algorithm: 'Random Forest',
    fileName: 'deliveries.xlsx',
    qualityScore: 87,
    pipelineProgress: 75,
  },
  {
    id: 'proj-3',
    title: 'Recommandation produits',
    useCaseDescription: 'Recommander des produits aux clients basé sur leur historique d\'achat',
    analysisType: 'clustering',
    timeHorizon: '1 mois',
    sector: 'retail',
    status: 'preparation',
    createdAt: '2025-02-20',
    rowCount: 0,
    columnCount: 0,
    algorithm: '',
    fileName: '',
    qualityScore: 0,
    pipelineProgress: 15,
  },
];

export const mockNLQResponses: Record<string, { text: string; chartData: { name: string; value: number }[] }> = {
  default: {
    text: `## Analyse du Risque de Churn

D'après le modèle XGBoost entraîné sur vos données (AUC = 0.89), voici les principaux facteurs de risque :

### Facteurs clés identifiés
1. **Type de contrat mensuel** — Les clients en contrat month-to-month ont un taux de churn 3.2x supérieur
2. **Score de satisfaction < 5** — Fortement corrélé avec le churn (OR = 4.1)
3. **Ancienneté < 12 mois** — Les nouveaux clients sont 2.5x plus à risque

### Recommandations
- Proposer une offre de fidélisation aux clients en contrat mensuel avec ancienneté < 6 mois
- Mettre en place un programme proactif pour les clients avec un score NPS < 5
- Surveiller les clients avec plus de 2 tickets support ouverts`,
    chartData: [
      { name: 'Type contrat', value: 28 },
      { name: 'Ancienneté', value: 22 },
      { name: 'Charges', value: 18 },
      { name: 'Satisfaction', value: 12 },
      { name: 'Connexion', value: 9 },
      { name: 'Internet', value: 6 },
      { name: 'Support', value: 5 },
    ],
  },
};

export function detectSector(useCase: string): string {
  const lower = useCase.toLowerCase();
  if (/churn|client|abonn|banque|crédit|paiement|finance|risque/i.test(lower)) return 'finance';
  if (/retard|livraison|transport|itinéraire|flotte|logistique/i.test(lower)) return 'transport';
  if (/produit|vente|retail|recommandation|panier|boutique/i.test(lower)) return 'retail';
  if (/maintenance|panne|machine|usine|manufacturing|production/i.test(lower)) return 'manufacturing';
  if (/dossier|administration|public|délai|service public/i.test(lower)) return 'public';
  return 'finance';
}
