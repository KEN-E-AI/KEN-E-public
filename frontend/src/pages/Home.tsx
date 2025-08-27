import { useState } from "react";
import HomeLayout from "@/components/home/HomeLayout";
import HomeChatArea from "@/components/home/HomeChatArea";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";

const Home = () => {
  const navigate = useNavigate();
  const { selectedOrgAccount } = useAuth();
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

  if (!selectedOrgAccount) {
    navigate("/organization-selection");
    return null; // Prevent rendering while redirecting
  }

  return (
    <HomeLayout
      dateRange={dateRange}
      setDateRange={setDateRange}
      comparisonDateRange={comparisonDateRange}
      setComparisonDateRange={setComparisonDateRange}
    >
      <HomeChatArea />
    </HomeLayout>
  );
};

export default Home;
