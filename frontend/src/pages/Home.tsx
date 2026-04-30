import HomeChatArea from "@/components/home/HomeChatArea";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";

const Home = () => {
  const navigate = useNavigate();
  const { selectedOrgAccount } = useAuth();

  if (!selectedOrgAccount) {
    navigate("/organization-selection");
    return null;
  }

  return <HomeChatArea />;
};

export default Home;
