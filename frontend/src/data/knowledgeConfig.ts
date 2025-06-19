import { Product } from "@/types/knowledge";

export const products: Product[] = [
  {
    id: "google-analytics",
    name: "Google Analytics",
    description: "Website and app analytics platform",
    connected: true,
    icon: "🅖",
  },
  {
    id: "google-ads",
    name: "Google Ads",
    description: "Pay-per-click advertising platform",
    connected: true,
    icon: "🅖",
  },
  {
    id: "bing-ads",
    name: "Bing Ads",
    description: "Microsoft advertising platform",
    connected: false,
    icon: "Ⓑ",
  },
  {
    id: "google-search-console",
    name: "Google Search Console",
    description: "Search performance monitoring",
    connected: true,
    icon: "🅖",
  },
  {
    id: "meta-ads",
    name: "Meta Ads",
    description: "Facebook and Instagram advertising",
    connected: false,
    icon: "Ⓜ",
  },
];
