// Kept apart from load.ts so the client Tabs component doesn't pull in the server-only data source.
export const TABS = [["feed", "Feed"], ["patterns", "Patterns"], ["themes", "Themes"], ["insights", "Insights"]] as const;
