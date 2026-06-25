// Types mirroring the pipeline's JSON outputs (pipeline/insights.py +
// pipeline/run.py). These are the contract the dashboard reads from the
// committed snapshot in `data/`. Kept in sync by hand — the pipeline is the
// source of truth, so widen/adjust here if the emitter changes.

export type Sentiment = "positive" | "neutral" | "negative";

export type SentimentCounts = Record<Sentiment, number>;

/** One classified mention (an element of data/classified.json). */
export interface Mention {
  date: string | null;
  url: string;
  source: string;
  title: string;
  opening_text: string;
  hit_sentence: string;
  text: string;
  driver: string;
  sub_driver: string;
  sentiment: Sentiment;
  /** The dataset's original label, kept for the accuracy check. */
  sentiment_given: Sentiment | null;
  relevant: boolean;
  needs_review: boolean;
  confidence: number;
  rationale: string;
  reach: number | null;
}

export interface DriverStat {
  name: string;
  count: number;
  percentage: number;
  sentiment: SentimentCounts;
}

export interface SubDriverStat extends DriverStat {
  driver: string;
}

export interface DriverScore extends SubDriverStat {
  net_score: number;
  net_per_mention: number;
}

export interface SourceStat {
  name: string;
  count: number;
}

export interface ThemeStat {
  term: string;
  count: number;
}

export interface SentimentAgreement {
  compared: number;
  agree: number;
  accuracy: number;
  by_given_label: Record<
    string,
    { total: number; agree: number; accuracy: number }
  >;
}

/** The whole data/insights.json document. */
export interface Insights {
  brand: string;
  provider: string;
  generated_at: string;
  totals: {
    total_mentions: number;
    relevant: number;
    irrelevant: number;
    needs_review: number;
    total_reach: number;
    reach_known: number;
  };
  sentiment: {
    counts: SentimentCounts;
    percentages: SentimentCounts;
    net: number;
  };
  drivers: DriverStat[];
  sub_drivers: SubDriverStat[];
  sources: SourceStat[];
  themes: ThemeStat[];
  top_positive_drivers: DriverScore[];
  top_negative_drivers: DriverScore[];
  key_findings: string[];
  sentiment_agreement: SentimentAgreement;
}
