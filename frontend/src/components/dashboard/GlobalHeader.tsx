import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  User,
  Edit2,
  ChevronDown,
  Home,
  BarChart3,
  TrendingUp,
  Target,
  Search,
  BookOpen,
  Settings,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface GlobalHeaderProps {
  dateRange: { from: Date; to: Date };
  setDateRange: (range: { from: Date; to: Date }) => void;
  comparisonDateRange?: { from: Date; to: Date };
  setComparisonDateRange?: (range: { from: Date; to: Date }) => void;
  selectedAccount?: string;
  setSelectedAccount?: (accountId: string) => void;
}

export const accounts = [
  { id: "acme-corp", name: "Acme Corporation" },
  { id: "digital-solutions", name: "Digital Solutions Inc" },
  { id: "tech-startup", name: "TechStartup LLC" },
  { id: "marketing-agency", name: "Marketing Agency Pro" },
];

const navigationMenuItems = [
  { id: "home", name: "Home", icon: Home },
  { id: "overview", name: "Overview", icon: BarChart3 },
  { id: "marketing-funnel", name: "Performance Details", icon: TrendingUp },
  { id: "big-bets", name: "Big Bets", icon: Target },
  { id: "data-exploration", name: "Data Exploration", icon: Search },
  { id: "knowledge-base", name: "Knowledge Base", icon: BookOpen },
  { id: "settings", name: "Settings", icon: Settings },
];

const AccountDropdown = ({
  selectedAccount,
  setSelectedAccount,
}: {
  selectedAccount: string;
  setSelectedAccount: (accountId: string) => void;
}) => {
  const currentAccount = accounts.find(
    (account) => account.id === selectedAccount,
  );

  return (
    <Select value={selectedAccount} onValueChange={setSelectedAccount}>
      <SelectTrigger className="h-auto p-1 border-none shadow-none text-sm font-medium text-dashboard-gray-900 hover:bg-dashboard-gray-50 w-auto bg-transparent">
        <SelectValue>
          <div className="truncate max-w-[120px] gap-1">
            {currentAccount?.name}
          </div>
        </SelectValue>
      </SelectTrigger>
      <SelectContent align="end">
        {accounts.map((account) => (
          <SelectItem key={account.id} value={account.id}>
            {account.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

const GlobalHeader = ({
  dateRange,
  setDateRange,
  comparisonDateRange,
  setComparisonDateRange = () => {},
  selectedAccount = "acme-corp",
  setSelectedAccount = () => {},
}: GlobalHeaderProps) => {
  const navigate = useNavigate();
  return (
    <div className="bg-white border border-dashboard-gray-200 rounded-lg px-6 py-4">
      {/* Top Row - Navigation and User */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-semibold text-dashboard-gray-900">
            Measurement Strategy
          </h1>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <AccountDropdown
            selectedAccount={selectedAccount}
            setSelectedAccount={setSelectedAccount}
          />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z"
                  />
                </svg>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  // Handle PDF download
                  console.log("Download PDF");
                }}
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                <span>Download PDF</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  // Handle Slack sharing
                  console.log("Share in Slack");
                }}
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
                <span>Share in Slack</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="p-2">
                <User className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Your Name</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  // Handle invite users
                  console.log("Invite Users");
                }}
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"
                  />
                </svg>
                <span>Invite Users</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  // Handle user settings
                  console.log("Your Settings");
                }}
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                <span>Your Settings</span>
              </DropdownMenuItem>
              <DropdownMenuItem
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => {
                  // Handle sign out
                  console.log("Sign Out");
                }}
              >
                <svg
                  className="h-4 w-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                <span>Sign Out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="p-2">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <line
                    x1="4"
                    x2="20"
                    y1="12"
                    y2="12"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                  <line
                    x1="4"
                    x2="20"
                    y1="6"
                    y2="6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                  <line
                    x1="4"
                    x2="20"
                    y1="18"
                    y2="18"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                  />
                </svg>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {navigationMenuItems.map((item, index) => {
                const Icon = item.icon;
                return (
                  <div key={item.id}>
                    <DropdownMenuItem
                      className="flex items-center gap-3 cursor-pointer"
                      onClick={() => {
                        // Handle navigation
                        if (item.id === "knowledge-base") {
                          navigate("/knowledge-base");
                        } else if (item.id === "home") {
                          navigate("/");
                        } else {
                          console.log(`Navigate to ${item.name}`);
                        }
                      }}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{item.name}</span>
                    </DropdownMenuItem>
                    {index === navigationMenuItems.length - 2 && (
                      <DropdownMenuSeparator />
                    )}
                  </div>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </div>
  );
};

export default GlobalHeader;
