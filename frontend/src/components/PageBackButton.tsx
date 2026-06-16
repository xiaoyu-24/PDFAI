import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useNavigate } from "react-router-dom";

interface PageBackButtonProps {
  label?: string;
  fallbackTo?: string;
}

export default function PageBackButton({
  label = "返回",
  fallbackTo = "/",
}: PageBackButtonProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(fallbackTo);
  };

  return <Button icon={<ArrowLeftOutlined />} onClick={handleClick}>{label}</Button>;
}
