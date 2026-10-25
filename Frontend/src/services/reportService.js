import { apiRequest } from "./apiClient.js";

export function createReport(
  accessToken,
  {
    targetType,
    targetId,
    category,
    description,
    includeLimitedContext = false,
    evidence = [],
  },
) {
  const formData = new FormData();

  formData.append("target_type", targetType);
  formData.append("target_id", String(targetId));
  formData.append("category", category);
  formData.append("description", description);
  formData.append(
    "include_limited_context",
    String(Boolean(includeLimitedContext)),
  );

  evidence.forEach((file) => {
    formData.append("evidence", file);
  });

  return apiRequest("/reports", {
    method: "POST",
    accessToken,
    body: formData,
  });
}

export function getMyReports(
  accessToken,
  {
    status = "",
    cursor = "",
    limit = 20,
  } = {},
) {
  const params = new URLSearchParams({
    limit: String(limit),
  });

  if (status) {
    params.set("status", status);
  }

  if (cursor) {
    params.set("cursor", cursor);
  }

  return apiRequest(
    `/reports?${params.toString()}`,
    {
      method: "GET",
      accessToken,
    },
  );
}

export function getMyReport(
  accessToken,
  reportId,
) {
  return apiRequest(
    `/reports/${encodeURIComponent(reportId)}`,
    {
      method: "GET",
      accessToken,
    },
  );
}
