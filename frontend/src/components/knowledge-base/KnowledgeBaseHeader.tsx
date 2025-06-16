import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  User,
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

const accounts = [
  { id: "acme-corp", name: "Acme Corporation" },
  { id: "digital-solutions", name: "Digital Solutions Inc" },
  { id: "tech-startup", name: "TechStartup LLC" },
  { id: "marketing-agency", name: "Marketing Agency Pro" },
];

const navigationMenuItems = [
  { id: "home", name: "Home", icon: Home },
  { id: "overview", name: "Overview", icon: BarChart3 },
  { id: "marketing-funnel", name: "Marketing Funnel", icon: TrendingUp },
  { id: "big-bets", name: "Big Bets", icon: Target },
  { id: "data-exploration", name: "Data Exploration", icon: Search },
  { id: "knowledge-base", name: "Knowledge Base", icon: BookOpen },
  { id: "settings", name: "Settings", icon: Settings },
];

const AccountDropdown = () => {
  const [selectedAccount, setSelectedAccount] = useState("acme-corp");
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

const KnowledgeBaseHeader = () => {
  const navigate = useNavigate();

  return (
    <div className="bg-white border border-dashboard-gray-200 rounded-lg m-3 sm:m-6 mb-0 px-3 sm:px-6 py-3 sm:py-4">
      {/* Top Row - Navigation and User */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 sm:gap-4 min-w-0 flex-1">
          <h1 className="text-lg sm:text-2xl font-semibold text-dashboard-gray-900 truncate">
            Knowledge Base
          </h1>
        </div>

        <div className="flex items-center gap-1 sm:gap-3 flex-shrink-0">
          <div className="hidden sm:block">
            <AccountDropdown />
          </div>

          {/* Mobile Account Dropdown */}
          <div className="sm:hidden">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="p-2">
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
                      d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                    />
                  </svg>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {accounts.map((account) => (
                  <DropdownMenuItem key={account.id}>
                    {account.name}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

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
                        } else if (item.id === "marketing-funnel") {
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

export default KnowledgeBaseHeader;
