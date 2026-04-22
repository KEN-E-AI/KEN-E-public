import googleAdsLogo from '@/imports/logo_--_Google_Ads.png';
import salesforceLogo from '@/imports/logo_--_salesforce.png';
import mailchimpLogo from '@/imports/logo_--_mailchimp.png';
import hubspotLogo from '@/imports/logo_--_hubspot.png';
import linkedinLogo from '@/imports/logo_--_linkedin.png';
import metaLogo from '@/imports/logo_--_Meta.png';
import gscLogo from '@/imports/logo_--_google_search_console.png';
import bingLogo from '@/imports/logo_--_bing.png';
import shopifyLogo from '@/imports/logo_--_shopify.png';

const logoOverrides: Record<string, string> = {
  'Google Ads': googleAdsLogo,
  'Salesforce': salesforceLogo,
  'Mailchimp': mailchimpLogo,
  'HubSpot': hubspotLogo,
  'LinkedIn Ads': linkedinLogo,
  'Meta Ads': metaLogo,
  'Google Search Console': gscLogo,
  'Bing Ads': bingLogo,
  'Shopify': shopifyLogo,
};

interface IntegrationIconProps {
  name: string;
  fallbackEmoji: string;
  className?: string;
}

export function IntegrationIcon({ name, fallbackEmoji, className = 'size-10' }: IntegrationIconProps) {
  const logo = logoOverrides[name];
  if (logo) {
    return <img src={logo} alt={name} className={`${className} object-contain`} />;
  }
  return <span className="text-3xl">{fallbackEmoji}</span>;
}