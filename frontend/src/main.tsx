import { StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import "./i18n";
import Layout from "./components/Layout";
import Home from "./routes/Home";
import { RouteError } from "./components/ErrorPanel";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5 * 60_000, refetchOnWindowFocus: false } },
});

const router = createBrowserRouter([
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Home /> },
      { path: "reading", lazy: async () => ({ Component: (await import("./routes/Reading")).default }) },
      { path: "check", lazy: async () => ({ Component: (await import("./routes/Check")).default }) },
      { path: "manual", lazy: async () => ({ Component: (await import("./routes/Manual")).default }) },
      { path: "plan/:id", lazy: async () => ({ Component: (await import("./routes/PlanPage")).default }) },
      { path: "*", lazy: async () => ({ Component: (await import("./routes/NotFound")).default }) },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="min-h-dvh bg-paper" />}>
        <RouterProvider router={router} />
      </Suspense>
    </QueryClientProvider>
  </StrictMode>,
);
