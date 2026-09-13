import { defineStore } from "pinia";

import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
} from "../api/client";

export const useCatalogStore = defineStore("catalog", {
  state: () => ({
    providers: [],
    models: [],
    defaultParams: {},
    loading: false,
  }),
  actions: {
    async loadProviders() {
      this.providers = await apiGet("/api/providers");
    },
    async loadModels() {
      this.models = await apiGet("/api/models");
    },
    async loadDefaultParams() {
      this.defaultParams = await apiGet("/api/default-params");
    },
    async loadAll() {
      this.loading = true;
      try {
        await Promise.all([
          this.loadProviders(),
          this.loadModels(),
          this.loadDefaultParams(),
        ]);
      } finally {
        this.loading = false;
      }
    },
    async createProvider(payload) {
      const provider = await apiPost("/api/providers", payload);
      await this.loadProviders();
      await this.loadModels();
      return provider;
    },
    async updateProvider(id, patch) {
      const provider = await apiPatch(`/api/providers/${id}`, patch);
      await this.loadProviders();
      await this.loadModels();
      return provider;
    },
    async deleteProvider(id) {
      await apiDelete(`/api/providers/${id}`);
      await this.loadProviders();
      await this.loadModels();
    },
    async addModel(providerId, payload) {
      const model = await apiPost(`/api/providers/${providerId}/models`, payload);
      await this.loadProviders();
      await this.loadModels();
      return model;
    },
    async updateModel(providerId, modelRowId, patch) {
      const model = await apiPatch(
        `/api/providers/${providerId}/models/${modelRowId}`,
        patch
      );
      await this.loadProviders();
      await this.loadModels();
      return model;
    },
    async deleteModel(providerId, modelRowId) {
      await apiDelete(`/api/providers/${providerId}/models/${modelRowId}`);
      await this.loadProviders();
      await this.loadModels();
    },
    testModel(providerId, modelRowId) {
      return apiPost(
        `/api/providers/${providerId}/models/${modelRowId}/test`
      );
    },
  },
});
