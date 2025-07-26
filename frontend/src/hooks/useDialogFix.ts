import { useEffect } from "react";

/**
 * Hook to fix dialog-related issues like focus trapping and overlay persistence
 */
export const useDialogFix = () => {
  // Global function to force fix frozen UI
  (window as any).fixFrozenUI = () => {
    console.log("[fixFrozenUI] Force fixing frozen UI...");
    
    // Remove all portal elements
    document.querySelectorAll('[data-radix-portal]').forEach(el => el.remove());
    
    // Reset body styles
    document.body.style.pointerEvents = '';
    document.body.style.overflow = '';
    document.body.style.position = '';
    
    // Remove any elements that might be blocking interaction
    document.querySelectorAll('[role="dialog"], [data-state="open"], [aria-hidden="true"]').forEach(el => {
      if (el.getAttribute('data-radix-portal') || el.closest('[data-radix-portal]')) {
        el.remove();
      }
    });
    
    // Force reflow
    document.body.offsetHeight;
    
    console.log("[fixFrozenUI] UI should be unfrozen now");
  };
  useEffect(() => {
    // Function to clean up any lingering dialog artifacts
    const cleanupDialogs = () => {
      // Remove any orphaned dialog overlays
      const overlays = document.querySelectorAll('[data-radix-portal] [role="dialog"]');
      const dialogBackdrops = document.querySelectorAll('[data-radix-portal] [data-aria-hidden="true"]');
      
      console.log(`[useDialogFix] Found ${overlays.length} dialog overlays and ${dialogBackdrops.length} backdrops`);
      
      // Check if body has pointer-events disabled
      const bodyStyle = document.body.style;
      if (bodyStyle.pointerEvents === "none") {
        console.warn("[useDialogFix] Body pointer-events were disabled, resetting...");
        bodyStyle.pointerEvents = "";
      }
      
      // Check for any elements with data-state="open" but no visible dialog
      const openElements = document.querySelectorAll('[data-state="open"]');
      openElements.forEach((el) => {
        const isVisible = el.getBoundingClientRect().width > 0;
        if (!isVisible) {
          console.warn("[useDialogFix] Found hidden element with data-state='open', removing...", el);
          el.remove();
        }
      });
    };

    // Run cleanup after a delay to catch any lingering issues
    const timer = setInterval(cleanupDialogs, 1000);
    
    // Also run on click to immediately fix frozen states
    const handleClick = () => {
      cleanupDialogs();
    };
    
    document.addEventListener("click", handleClick);
    
    return () => {
      clearInterval(timer);
      document.removeEventListener("click", handleClick);
    };
  }, []);
};