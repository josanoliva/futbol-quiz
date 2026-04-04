import fs from "fs";
import path from "path";

export type AffiliateItem = {
  id: string;
  title: string;
  description: string;
  url: string;
  cta: string;
};

export type AffiliateBlock = {
  title: string;
  description: string;
  items: AffiliateItem[];
};

const affiliateFile = path.join(process.cwd(), "data", "affiliate-block.json");

export function getAffiliateBlock(): AffiliateBlock | null {
  if (!fs.existsSync(affiliateFile)) return null;

  const raw = fs.readFileSync(affiliateFile, "utf-8");
  return JSON.parse(raw) as AffiliateBlock;
}