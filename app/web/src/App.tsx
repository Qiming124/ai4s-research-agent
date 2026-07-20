import { useEffect, useState } from "react";
import { ChatPage } from "./components/ChatPage";
import { ApiLabPage } from "./components/ApiLabPage";
import { ErrorBoundary } from "./components/ErrorBoundary";

function readRoute(): "chat" | "api-lab" {
  const hash = window.location.hash.replace(/^#/, "") || "/";
  if (hash === "/api-lab" || hash.startsWith("/api-lab?")) return "api-lab";
  return "chat";
}

export default function App() {
  const [route, setRoute] = useState<"chat" | "api-lab">(readRoute);

  useEffect(() => {
    const onHash = () => setRoute(readRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <ErrorBoundary>
      {route === "api-lab" ? (
        <ApiLabPage onBack={() => { window.location.hash = "#/"; }} />
      ) : (
        <ChatPage />
      )}
    </ErrorBoundary>
  );
}
