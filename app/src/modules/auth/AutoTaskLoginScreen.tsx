import { Bot } from "lucide-react";
import { useEffect, useState } from "react";
import {
  login as authLogin,
  getAuthEndpointConfig,
  saveAuthEndpointConfig,
} from "@/actions/auth";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { AutoTaskEndpointConfig } from "@/types/endpoint-config";
import { defaultAutoTaskEndpointConfig } from "@/types/endpoint-config";
import { EndpointConfigPanel } from "./components/EndpointConfigPanel";
import { LoginForm } from "./components/LoginForm";
import {
  getLastLoginAccount,
  saveLastLoginAccount,
} from "./last-login-account";

interface AutoTaskLoginScreenProps {
  onLoginSuccess: () => void;
}

export function AutoTaskLoginScreen({
  onLoginSuccess,
}: AutoTaskLoginScreenProps) {
  const [endpointConfig, setEndpointConfig] = useState<AutoTaskEndpointConfig>(
    defaultAutoTaskEndpointConfig
  );

  useEffect(() => {
    getAuthEndpointConfig()
      .then(setEndpointConfig)
      .catch(() => {
        // use defaults
      });
  }, []);

  const handleLogin = async (account: string, password: string) => {
    await saveAuthEndpointConfig(endpointConfig);
    await authLogin(account, password);
    saveLastLoginAccount(account);
    onLoginSuccess();
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Bot className="h-6 w-6" />
          </div>
          <CardTitle>AutoTask Studio</CardTitle>
          <CardDescription>使用 nodeskclaw 账号登录</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <LoginForm
            defaultAccount={getLastLoginAccount()}
            onSubmit={handleLogin}
          />
          <EndpointConfigPanel
            config={endpointConfig}
            onChange={setEndpointConfig}
          />
        </CardContent>
      </Card>
    </div>
  );
}
