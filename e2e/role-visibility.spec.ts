import { expect, test, type Page } from "@playwright/test";
import type { Role } from "@/types";

const createdAt = "2026-01-01T00:00:00Z";
const item = {
  id: 1,
  name: "Demo item",
  sku: "DEMO-001",
  categoryId: 1,
  categoryName: "Tools",
  supplierId: 1,
  supplierName: "Demo supplier",
  locationId: 1,
  locationName: "A-01",
  locations: [{ locationId: 1, locationName: "A-01", quantity: 12 }],
  stock: 12,
  minStock: 2,
  price: 10,
  description: "",
  status: "ok",
  createdAt,
  updatedAt: createdAt,
};
const userNames: Record<Role, string> = {
  LIETOTAJS: "Read Only",
  VADITAJS: "Manager",
  ADMIN: "Administrator",
};

async function loginAs(page: Page, role: Role) {
  const user = {
    id: role === "LIETOTAJS" ? 1 : role === "VADITAJS" ? 2 : 3,
    name: userNames[role],
    email: `${role.toLowerCase()}@example.test`,
    role,
    isActive: true,
    createdAt,
  };

  await page.route("**/api/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname.replace("/api/", "");
    let body: unknown = {};
    switch (pathname) {
      case "auth/login":
        body = { accessToken: "test-token", tokenType: "bearer", user };
        break;
      case "auth/me":
        body = user;
        break;
      case "dashboard":
        body = { totalItems: 1, totalUnits: 12, lowStockCount: 0, criticalStockCount: 0, activeTransfers: 1, stockValue: 120, activities: [] };
        break;
      case "items":
        body = { items: [item], total: 1, page: 1, pageSize: 10 };
        break;
      case "categories":
        body = [{ id: 1, name: "Tools", description: "", icon: "Package", color: "blue", itemCount: 1, createdAt }];
        break;
      case "suppliers":
        body = [{ id: 1, name: "Demo supplier", contactPerson: "A Person", email: "supplier@example.test", phone: "+371 20000000", address: "Riga, Latvia", category: "Tools", paymentTerms: "net30", isActive: true, createdAt }];
        break;
      case "locations":
        body = [{ id: 1, code: "A-01", name: "Aisle A", capacity: 100, usedCapacity: 12, createdAt }, { id: 2, code: "B-01", name: "Aisle B", capacity: 100, usedCapacity: 0, createdAt }];
        break;
      case "transfers":
        body = [{ id: 1, code: "TR-0001", itemId: 1, itemName: item.name, sourceLocationId: 1, sourceLocationName: "A-01", destinationLocationId: 2, destinationLocationName: "B-01", quantity: 2, status: "pending", priority: "normal", notes: "", creatorName: "Manager", createdAt, updatedAt: createdAt }];
        break;
      case "users":
        body = [
          { ...user, role: "LIETOTAJS", id: 1, name: "Read Only" },
          { ...user, role: "VADITAJS", id: 2, name: "Manager" },
          { ...user, role: "ADMIN", id: 3, name: "Administrator", email: "admin@example.test" },
        ];
        break;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });

  await page.goto("/login");
  await page.getByLabel("E-pasts").fill(user.email);
  await page.getByLabel("Parole").fill("Test1234");
  await page.getByRole("button", { name: "Pieslēgties" }).click();
  await expect(page.getByRole("heading", { name: "Informācijas panelis" })).toBeVisible();
}

test("LIETOTAJS can read but has no mutation or admin controls", async ({ page }) => {
  await loginAs(page, "LIETOTAJS");
  await expect(page.getByText("Lietotājs", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Lietotāji" })).toHaveCount(0);

  await page.goto("/items");
  await expect(page.getByRole("button", { name: "Pievienot preci" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Labot|Dzēst/ })).toHaveCount(0);
  await expect(page.getByText("Demo item")).toBeVisible();

  await page.goto("/transfers");
  await expect(page.getByRole("button", { name: "Izveidot" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Nosūtīt|Pabeigt|Atcelt/ })).toHaveCount(0);
  await expect(page.getByText("TR-0001")).toBeVisible();
});

test("VADITAJS retains operations without administrator pages", async ({ page }) => {
  await loginAs(page, "VADITAJS");
  await expect(page.getByText("Vadītājs", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Lietotāji" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Iestatījumi" })).toHaveCount(0);

  await page.goto("/items");
  await expect(page.getByRole("button", { name: "Pievienot preci" })).toBeVisible();
  await page.goto("/transfers");
  await expect(page.getByRole("button", { name: "Izveidot" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Nosūtīt" })).toBeVisible();
});

test("ADMIN sees administrative navigation and three role choices", async ({ page }) => {
  await loginAs(page, "ADMIN");
  await expect(page.getByText("Administrators", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Lietotāji" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Iestatījumi" })).toBeVisible();

  await page.goto("/users");
  await expect(page.getByRole("button", { name: "Pievienot lietotāju" })).toBeVisible();
  await expect(page.getByText("Lietotājs", { exact: true })).toBeVisible();
  await expect(page.getByText("Vadītājs", { exact: true })).toBeVisible();
  await expect(page.getByText("Administrators", { exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Mainīt Administrator lomu" })).toBeDisabled();
});
