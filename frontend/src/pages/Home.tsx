import { useState } from "react";
import HomeLayout from "@/components/home/HomeLayout";
import HomeChatArea from "@/components/home/HomeChatArea";

const Home = () => {
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
    <HomeLayout
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
      selectedAccount={selectedAccount}
      setSelectedAccount={setSelectedAccount}
    >
      <HomeChatArea />
    </HomeLayout>
  );
};

export default Home;
