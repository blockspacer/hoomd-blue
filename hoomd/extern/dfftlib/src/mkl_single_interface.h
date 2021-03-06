/* MKL (single precision) backend for distributed FFT
 */

#ifndef __DFFT_MKL_SINGLE_INTERFACE_H__
#define __DFFT_MKL_SINGLE_INTERFACE_H__

#include <omp.h>
#include <mkl.h>

#pragma GCC visibility push(default)

#define FFT1D_SUPPORTS_THREADS

typedef MKL_Complex8  cpx_t;
typedef DFTI_DESCRIPTOR_HANDLE plan_t;

#define RE(X) X.real
#define IM(X) X.imag

/* Initialize the library
 */
int dfft_init_local_fft();

/* De-initialize the library
 */
void dfft_teardown_local_fft();

/* Create a FFTW plan
 *
 * sign = 0 (forward) or 1 (inverse)
 */
int dfft_create_1d_plan(
    plan_t *plan,
    int dim,
    int howmany,
    int istride,
    int idist,
    int ostride,
    int odist,
    int dir);

int dfft_allocate_aligned_memory(cpx_t **ptr, size_t size);

void dfft_free_aligned_memory(cpx_t *ptr);

/* Destroy a 1d plan */
void dfft_destroy_1d_plan(plan_t *p);

/* Excecute a local 1D FFT
 */
void dfft_local_1dfft(
    cpx_t *in,
    cpx_t *out,
    plan_t p,
    int dir);

#pragma GCC visibility pop
#endif
