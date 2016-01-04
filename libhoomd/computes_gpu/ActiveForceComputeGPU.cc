/*
Highly Optimized Object-oriented Many-particle Dynamics -- Blue Edition
(HOOMD-blue) Open Source Software License Copyright 2009-2015 The Regents of
the University of Michigan All rights reserved.

HOOMD-blue may contain modifications ("Contributions") provided, and to which
copyright is held, by various Contributors who have granted The Regents of the
University of Michigan the right to modify and/or distribute such Contributions.

You may redistribute, use, and create derivate works of HOOMD-blue, in source
and binary forms, provided you abide by the following conditions:

* Redistributions of source code must retain the above copyright notice, this
list of conditions, and the following disclaimer both in the code and
prominently in any materials provided with the distribution.

* Redistributions in binary form must reproduce the above copyright notice, this
list of conditions, and the following disclaimer in the documentation and/or
other materials provided with the distribution.

* All publications and presentations based on HOOMD-blue, including any reports
or published results obtained, in whole or in part, with HOOMD-blue, will
acknowledge its use according to the terms posted at the time of submission on:
http://codeblue.umich.edu/hoomd-blue/citations.html

* Any electronic documents citing HOOMD-Blue will link to the HOOMD-Blue website:
http://codeblue.umich.edu/hoomd-blue/

* Apart from the above required attributions, neither the name of the copyright
holder nor the names of HOOMD-blue's contributors may be used to endorse or
promote products derived from this software without specific prior written
permission.

Disclaimer

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER AND CONTRIBUTORS ``AS IS'' AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND/OR ANY
WARRANTIES THAT THIS SOFTWARE IS FREE OF INFRINGEMENT ARE DISCLAIMED.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

// Maintainer: joaander


#include "ActiveForceComputeGPU.h"
#include "ActiveForceComputeGPU.cuh"

#include <boost/python.hpp>
#include <vector>
using namespace boost::python;

using namespace std;

/*! \file ActiveForceComputeGPU.cc
    \brief Contains code for the ActiveForceComputeGPU class
*/

/*! \param blah this does blah
*/   
ActiveForceComputeGPU::ActiveForceComputeGPU(boost::shared_ptr<SystemDefinition> sysdef, int seed, boost::python::list f_lst,
        bool orientation_link, Scalar rotation_diff, Scalar3 P, Scalar rx, Scalar ry, Scalar rz)
        : ActiveForceCompute(sysdef, seed, f_lst, orientation_link, rotation_diff, P, rx, ry, rz), m_block_size(256)
{
    if (!m_exec_conf->isCUDAEnabled())
        {
        m_exec_conf->msg->error() << "Creating a ActiveForceComputeGPU with no GPU in the execution configuration" << endl;
        throw std::runtime_error("Error initializing ActiveForceComputeGPU");
        }
}

/*! \param blah this does blah
*/
void ActiveForceComputeGPU::setForces()
{
    //  array handles
    ArrayHandle<Scalar3> d_actVec(m_activeVec, access_location::device, access_mode::read);
    ArrayHandle<Scalar> d_actMag(m_activeMag, access_location::device, access_mode::read);
    ArrayHandle<Scalar4> d_force(m_force,access_location::device,access_mode::overwrite);
    ArrayHandle<Scalar4> d_orientation(m_pdata->getOrientationArray(), access_location::device, access_mode::read);
    ArrayHandle<unsigned int> d_rtag(m_pdata->getRTags(), access_location::device, access_mode::read);
    
    // sanity check
    assert(d_force.data != NULL);
    assert(d_actVec.data != NULL);
    assert(d_actMag.data != NULL);
    assert(d_orientation.data != NULL);
    assert(d_rtag.data != NULL);
    
    bool orientationLink = (m_orientationLink == true && m_sysdef->getRigidData()->getNumBodies() > 0);
    unsigned int N = m_pdata->getN();
    
    gpu_compute_active_force_set_forces(N,
                                     d_rtag.data,
                                     d_force.data,
                                     d_orientation.data,
                                     d_actVec.data,
                                     d_actMag.data,
                                     m_P,
                                     m_rx,
                                     m_ry,
                                     m_rz,
                                     orientationLink,
                                     m_block_size);
}

/*! \param blah this does blah
*/
void ActiveForceComputeGPU::rotationalDiffusion(unsigned int timestep)
{
    //  array handles
    ArrayHandle<Scalar3> d_actVec(m_activeVec, access_location::host, access_mode::readwrite);
    ArrayHandle<Scalar> d_actMag(m_activeMag, access_location::host, access_mode::read);
    ArrayHandle<Scalar4> d_pos(m_pdata -> getPositions(), access_location::host, access_mode::read);
    ArrayHandle<unsigned int> d_rtag(m_pdata->getRTags(), access_location::device, access_mode::read);
    ArrayHandle<Scalar4> d_force(m_force,access_location::device,access_mode::overwrite);

    assert(h_actVec.data != NULL);
    assert(h_actMag.data != NULL);
    assert(h_pos.data != NULL);
    assert(d_rtag.data != NULL);
    assert(d_force.data != NULL);
    
    bool is2D = (m_sysdef->getNDimensions() == 2);
    unsigned int N = m_pdata->getN();

    gpu_compute_active_force_rotational_diffusion(N,
                                                    d_rtag.data,
                                                    d_pos.data,
                                                    d_force.data,
                                                    d_actVec.data,
                                                    d_actMag.data,
                                                    m_P,
                                                    m_rx,
                                                    m_ry,
                                                    m_rz,
                                                    is2D,
                                                    m_rotationDiff,
                                                    m_deltaT,
                                                    timestep,
                                                    m_seed,
                                                    m_block_size);
}

/*! \param blah this does blah
*/
void ActiveForceComputeGPU::setConstraint()
{
    EvaluatorConstraintEllipsoid Ellipsoid(m_P, m_rx, m_ry, m_rz);
    
    //  array handles
    ArrayHandle<Scalar3> d_actVec(m_activeVec, access_location::device, access_mode::readwrite);
    ArrayHandle<Scalar> d_actMag(m_activeMag, access_location::device, access_mode::readwrite);
    ArrayHandle<Scalar4> d_pos(m_pdata -> getPositions(), access_location::device, access_mode::read);
    ArrayHandle<unsigned int> d_rtag(m_pdata->getRTags(), access_location::device, access_mode::read);
    ArrayHandle<Scalar4> d_force(m_force,access_location::device,access_mode::overwrite);

    assert(d_actVec.data != NULL);
    assert(d_actMag.data != NULL);
    assert(d_pos.data != NULL);
    assert(d_rtag.data != NULL);
    assert(d_force.data != NULL);
    const unsigned int N = m_pdata->getN();

    gpu_compute_active_force_set_constraints(N,
                                             d_rtag.data,
                                             d_pos.data,
                                             d_force.data,
                                             d_actVec.data,
                                             d_actMag.data,
                                             m_P,
                                             m_rx,
                                             m_ry,
                                             m_rz,
                                             m_block_size);
}

/*! This function calls setForces()
    \param timestep Current timestep
*/
void ActiveForceComputeGPU::computeForces(unsigned int timestep)
{
    if (m_prof) m_prof->push(m_exec_conf, "ActiveForceCompute");
    assert(m_pdata);
    
    ArrayHandle<unsigned int> d_rtag(m_pdata->getRTags(), access_location::device, access_mode::read);
    assert(d_rtag.data != NULL);

    if (shouldCompute(timestep))
    {
        // run the kernel in parallel on all GPUs
        if (m_rx != 0)
        {
            setConstraint(); // apply surface constraints to active particles active force vectors
        }
        if (m_rotationDiff != 0)
        {
            rotationalDiffusion(timestep); // apply rotational diffusion to active particles
        }
        setForces(); // set forces for particles
    }
    
    if(m_exec_conf->isCUDAErrorCheckingEnabled())
        CHECK_CUDA_ERROR();

    if (m_prof)
        m_prof->pop(m_exec_conf);
}


void export_ActiveForceComputeGPU()
{
    class_< ActiveForceComputeGPU, boost::shared_ptr<ActiveForceComputeGPU>, bases<ActiveForceCompute>, boost::noncopyable >
    ("ActiveForceComputeGPU", init< boost::shared_ptr<SystemDefinition>, int, boost::python::list, bool, Scalar,
                                    Scalar3,
                                    Scalar,
                                    Scalar,
                                    Scalar >())
    ;
}
