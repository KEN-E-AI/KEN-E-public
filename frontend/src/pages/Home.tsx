import { useState } from "react";
import GlobalHeader from "@/components/dashboard/GlobalHeader";
import NotificationsSidebar from "@/components/home/NotificationsSidebar";
import MainChat from "@/components/home/MainChat";

const Home = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [selectedAccount, setSelectedAccount] = useState("acme-corp");
  const [dateRange, setDateRange] = useState({
    from: new Date(2025, 0, 1),
    to: new Date(2025, 0, 31),
  });
  const [comparisonDateRange, setComparisonDateRange] = useState<
    | {
        from: Date;
        to: Date;
      }
    | undefined
  >(undefined);

  return (
    <div className="min-h-screen bg-slate-50">
      <GlobalHeader
        dateRange={dateRange}
        setDateRange={setDateRange}
        comparisonDateRange={comparisonDateRange}
        setComparisonDateRange={setComparisonDateRange}
        selectedAccount={selectedAccount}
        setSelectedAccount={setSelectedAccount}
      />

      <div className="flex h-[calc(100vh-80px)]">
        {/* Notifications Sidebar */}
        <div
          className={`${
            isSidebarOpen ? "w-64" : "w-0"
          } transition-all duration-300 ease-in-out overflow-hidden bg-white border-r border-gray-200`}
        >
          <NotificationsSidebar />
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col">
          <MainChat />
        </div>
      </div>
    </div>
  );
};

export default Home;
