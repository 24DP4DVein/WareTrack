export type Role = "USER" | "ADMIN";
export type ItemStatus = "ok" | "low" | "critical";
export type TransferStatus = "pending" | "in-transit" | "done" | "cancelled";
export type TransferPriority = "normal" | "high" | "urgent";
export interface User { id:number; name:string; email:string; role:Role; isActive:boolean; createdAt:string }
export interface AuthResponse { accessToken:string; tokenType:string; user:User }
export interface Category { id:number; name:string; description:string; icon:string; color:"blue"|"green"|"amber"|"red"|"purple"; itemCount:number; createdAt:string }
export interface Supplier { id:number; name:string; contactPerson:string; email:string; phone:string; address:string; category:string; paymentTerms:"net30"|"net60"|"cod"; isActive:boolean; createdAt:string }
export interface Location { id:number; code:string; name:string; capacity:number; usedCapacity:number; createdAt:string }
export interface Item { id:number; name:string; sku:string; categoryId:number; categoryName:string; supplierId:number|null; supplierName:string|null; locationId:number; locationName:string; stock:number; minStock:number; price:number; description:string; status:ItemStatus; createdAt:string; updatedAt:string }
export interface ItemInput { name:string; sku:string; categoryId:number; supplierId?:number|null; locationId:number; stock:number; minStock:number; price:number; description?:string }
export interface ItemList { items:Item[]; total:number; page:number; pageSize:number }
export interface Transfer { id:number; code:string; itemId:number; itemName:string; sourceLocationId:number; sourceLocationName:string; destinationLocationId:number; destinationLocationName:string; quantity:number; status:TransferStatus; priority:TransferPriority; notes:string; creatorName:string; createdAt:string; updatedAt:string }
export interface TransferInput { itemId:number; sourceLocationId:number; destinationLocationId:number; quantity:number; priority:TransferPriority; notes?:string }
export interface DashboardData { totalItems:number; totalUnits:number; lowStockCount:number; criticalStockCount:number; activeTransfers:number; stockValue:number; activities:{id:number;message:string;userName:string|null;createdAt:string}[] }
export interface ReportData { totalUnits:number; totalValue:number; completedTransfers:number; lowStockCount:number; categoryDistribution:{name:string;units:number}[]; topItems:{name:string;movement:number}[] }
export interface CategoryInput { name:string; description:string; icon:string; color:Category["color"] }
export interface SupplierInput { name:string; contactPerson:string; email:string; phone:string; address:string; category:string; paymentTerms:Supplier["paymentTerms"] }
export type CompanyRole = "LIETOTAJS" | "VADITAJS" | "ADMIN";
export type JoinRequestStatus = "PENDING" | "APPROVED" | "REJECTED";
export interface PublicCompany { id:number; name:string; slug:string }
export interface Company extends PublicCompany { isActive:boolean; createdAt:string; updatedAt:string }
export interface MyCompany extends PublicCompany { role:CompanyRole }
export interface JoinRequest { id:number; companyId:number; companyName:string; status:JoinRequestStatus; requestedAt:string; reviewedAt:string|null; rejectionReason:string|null }
export interface ManagedJoinRequest extends JoinRequest { userId:number; userName:string; userEmail:string }
export interface CompanyMembership { id:number; companyId:number; userId:number; userName:string; userEmail:string; role:Exclude<CompanyRole,"ADMIN">; isActive:boolean; approvedAt:string|null; revokedAt:string|null }
export interface LocationInput { code:string; name:string; capacity:number }
