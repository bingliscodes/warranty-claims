import { Navigate, Outlet, Route, Routes } from "react-router";
import { NavBar } from "@/components/NavBar";
import ProfilePage from "@/session/ProfilePage";
import RequireUser from "@/session/RequireUser";
import RolePickerPage from "@/session/RolePickerPage";

// Every page except /start needs a signed-in user, and shows the nav bar above it.
function SignedInLayout() {
  return (
    <RequireUser>
      <NavBar />
      <main className="mx-auto max-w-5xl p-4">
        <Outlet />
      </main>
    </RequireUser>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/start" element={<RolePickerPage />} />
      <Route element={<SignedInLayout />}>
        {/* Task 15 replaces this with the claims list. */}
        <Route path="/" element={<h1 className="text-2xl font-semibold">Claims</h1>} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
