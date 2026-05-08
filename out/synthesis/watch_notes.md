# EVE Vault tenant/localnet/signing refactor

**source:** evevault
**authority_tier:** official_tooling
**change_type:** wallet_environment_signing_refactor
**retrieved_at:** 2025-05-08T12:00:00Z
**categories:** tooling, wallet, eve-vault, tenant, localnet, signing, zklogin, stillness, utopia

## Summary

EVE Vault now appears to consolidate network/tenant selection into a context-based flow and changes signing utilities from ephSign/rawSign to signWithIntent/signForChain. Treat wallet/session/signing behavior as environment-scoped across Stillness, Utopia, and localnet.

## Diff Findings

- localnet: 49 changed records
- tenant: 30 changed records
- zkLogin: 28 changed records
- Stillness/Utopia references changed
- signing API changed from ephSign/rawSign to signWithIntent/signForChain

## Old Surfaces Removed

- useNetwork.ts — network selection hook removed
- useTenant.ts — tenant selection hook removed
- networkStore.ts — network state store removed
- runtime.ts — runtime configuration removed
- ephSign.ts — ephemeral signing utility removed
- rawSign.ts — raw signing utility removed

## New Surfaces Added

- useContext.ts — unified context hook for tenant/devMode/chain
- contextStore.ts — context state store replacing networkStore
- localnetDeviceStorage.ts — localnet device-specific storage
- signWithIntent.ts — intent-based signing (replaces ephSign/rawSign)
- signForChain.ts — chain-aware signing utility
- signForChain.test.ts — tests for chain-aware signing
- signWithIntent.test.ts — tests for intent-based signing
- contextStore.test.ts — tests for context store

## Impact

- tenant/network selection consolidated into context
- signing now appears intent-based and chain-aware
- environments: Stillness, Utopia, localnet

## FrontierWarden Impact

No immediate change unless wallet/session/signing APIs used by its integration change. FrontierWarden is a separate project and is not affected by this source-change note.

## Watch Item

Watch EVE Vault signing/session API changes. If FrontierWarden operator flows rely on EVE Vault or dAppKit signing wrappers, verify compatibility with signWithIntent/signForChain and environment-scoped wallet context before changing binding or extension-authorization UX.
